"""Repository for scraping website and scrape-result database operations."""
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.backend.database.models import ScrapeResult, ScrapingWebsite
from app.backend.models.schemas import ScrapeResultStatus, ScrapeRunResponse, ScrapeStatus

# Sentinel used to distinguish "not provided" from "explicitly set to None".
_UNSET: Any = object()


class ScrapingRepository:
    """Data-access layer for scraping entities.

    Mirrors the pattern established by ``ApiKeyRepository``: constructor
    accepts a ``Session``, all writes use ``db.add`` / ``db.commit`` /
    ``db.refresh``, all reads use ``db.query(...).filter(...)``.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Website CRUD
    # ------------------------------------------------------------------

    def create_website(
        self,
        url: str,
        name: str,
        scrape_interval_minutes: int | None = None,
        max_depth: int = 1,
        max_pages: int = 10,
        include_external: bool = False,
    ) -> ScrapingWebsite:
        """Insert a new website record and return it."""
        website = ScrapingWebsite(
            url=url,
            name=name,
            scrape_interval_minutes=scrape_interval_minutes,
            max_depth=max_depth,
            max_pages=max_pages,
            include_external=include_external,
        )
        self.db.add(website)
        self.db.commit()
        self.db.refresh(website)
        return website

    def get_all_websites(self) -> list[ScrapingWebsite]:
        """Return all active websites ordered by name."""
        return (
            self.db.query(ScrapingWebsite)
            .filter(ScrapingWebsite.is_active == True)  # noqa: E712
            .order_by(ScrapingWebsite.name)
            .all()
        )

    def get_website_by_id(self, website_id: int) -> ScrapingWebsite | None:
        """Return a single website by primary key, or None if not found."""
        return self.db.query(ScrapingWebsite).filter(ScrapingWebsite.id == website_id).first()

    def delete_website(self, website_id: int) -> bool:
        """Delete a website and all its results (cascade via relationship).

        Returns True if the website existed and was deleted, False otherwise.
        """
        website = self.get_website_by_id(website_id)
        if not website:
            return False
        self.db.delete(website)
        self.db.commit()
        return True

    def update_website(
        self,
        website_id: int,
        name: str | None = None,
        scrape_interval_minutes: int | None = _UNSET,
        is_active: bool | None = None,
        max_depth: int | None = None,
        max_pages: int | None = None,
        include_external: bool | None = None,
    ) -> ScrapingWebsite | None:
        """Partially update a website with the provided fields.

        Uses the ``_UNSET`` sentinel to distinguish "not provided" (leave
        unchanged) from ``None`` (clear the field). Returns the updated
        website, or None if not found.
        """
        website = self.get_website_by_id(website_id)
        if not website:
            return None
        if name is not None:
            website.name = name
        if scrape_interval_minutes is not _UNSET:
            website.scrape_interval_minutes = scrape_interval_minutes
        if is_active is not None:
            website.is_active = is_active
        if max_depth is not None:
            website.max_depth = max_depth
        if max_pages is not None:
            website.max_pages = max_pages
        if include_external is not None:
            website.include_external = include_external
        self.db.commit()
        self.db.refresh(website)
        return website

    def update_website_status(
        self,
        website_id: int,
        status: str,
        last_error: str | None = None,
        last_scraped_at: datetime | None = None,
    ) -> ScrapingWebsite | None:
        """Update scrape_status and optional error / timestamp fields.

        Returns the updated website, or None if not found.
        """
        website = self.get_website_by_id(website_id)
        if not website:
            return None
        website.scrape_status = status
        if last_error is not None:
            website.last_error = last_error
        if last_scraped_at is not None:
            website.last_scraped_at = last_scraped_at
        self.db.commit()
        self.db.refresh(website)
        return website

    # ------------------------------------------------------------------
    # Scrape-result operations
    # ------------------------------------------------------------------

    def create_scrape_result(
        self,
        website_id: int,
        content: str | None,
        content_length: int,
        status: str,
        error_message: str | None = None,
        page_url: str | None = None,
        depth: int = 0,
        parent_result_id: int | None = None,
        scrape_run_id: str | None = None,
    ) -> ScrapeResult:
        """Insert a new scrape result and return it."""
        result = ScrapeResult(
            website_id=website_id,
            content=content,
            content_length=content_length,
            status=status,
            error_message=error_message,
            page_url=page_url,
            depth=depth,
            parent_result_id=parent_result_id,
            scrape_run_id=scrape_run_id,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def get_results_for_website(self, website_id: int, limit: int = 20) -> list[ScrapeResult]:
        """Return results for a website ordered by scraped_at descending."""
        return (
            self.db.query(ScrapeResult)
            .filter(ScrapeResult.website_id == website_id)
            .order_by(ScrapeResult.scraped_at.desc())
            .limit(limit)
            .all()
        )

    def get_result_by_id(self, result_id: int) -> ScrapeResult | None:
        """Return a single scrape result by primary key, or None if not found."""
        return self.db.query(ScrapeResult).filter(ScrapeResult.id == result_id).first()

    # ------------------------------------------------------------------
    # Scheduling and maintenance helpers
    # ------------------------------------------------------------------

    def get_websites_due_for_scrape(self) -> list[ScrapingWebsite]:
        """Return active, non-in_progress websites whose next scrape time has passed.

        A website is considered due when:
        - ``scrape_interval_minutes`` is set (not None)
        - ``is_active`` is True
        - ``scrape_status`` is not "in_progress"
        - ``last_scraped_at`` is None (never scraped), OR
          ``last_scraped_at + interval`` is in the past

        Because SQLite does not support native interval arithmetic, the
        due-time threshold is evaluated in Python per candidate row.
        """
        now = datetime.now(timezone.utc)

        # Fetch all candidates (scheduled, active, not currently running).
        candidates = (
            self.db.query(ScrapingWebsite)
            .filter(
                ScrapingWebsite.scrape_interval_minutes.isnot(None),
                ScrapingWebsite.is_active == True,  # noqa: E712
                ScrapingWebsite.scrape_status != ScrapeStatus.IN_PROGRESS,
            )
            .all()
        )

        due = []
        for website in candidates:
            assert website.scrape_interval_minutes is not None  # narrowed above
            if website.last_scraped_at is None:
                due.append(website)
                continue
            last = website.last_scraped_at
            # Normalise to UTC-aware for comparison
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            next_due = last + timedelta(minutes=website.scrape_interval_minutes)
            if next_due <= now:
                due.append(website)
        return due

    def cleanup_old_results(self, website_id: int, keep: int = 50) -> int:
        """Delete all results beyond the ``keep`` most-recent for a website.

        Returns the count of deleted rows.
        """
        # Identify the IDs of the records to keep (most-recent ``keep`` rows).
        # Use .select() to produce a proper SELECT subquery for IN() usage.
        keep_select = (
            self.db.query(ScrapeResult.id)
            .filter(ScrapeResult.website_id == website_id)
            .order_by(ScrapeResult.scraped_at.desc())
            .limit(keep)
        )
        to_delete = (
            self.db.query(ScrapeResult)
            .filter(
                ScrapeResult.website_id == website_id,
                ~ScrapeResult.id.in_(keep_select),
            )
            .all()
        )
        count = len(to_delete)
        for row in to_delete:
            self.db.delete(row)
        if count:
            self.db.commit()
        return count

    def reset_stuck_in_progress(self) -> int:
        """Reset all websites stuck in "in_progress" back to "idle".

        Called on scheduler startup to recover from a previous crash.
        Returns the count of recovered websites.
        """
        stuck = (
            self.db.query(ScrapingWebsite)
            .filter(ScrapingWebsite.scrape_status == ScrapeStatus.IN_PROGRESS)
            .all()
        )
        for website in stuck:
            website.scrape_status = ScrapeStatus.IDLE
        if stuck:
            self.db.commit()
        return len(stuck)

    # ------------------------------------------------------------------
    # Run-based queries
    # ------------------------------------------------------------------

    def get_results_by_run(self, scrape_run_id: str) -> list[ScrapeResult]:
        """Return all results for a given run ordered by (depth, id)."""
        return (
            self.db.query(ScrapeResult)
            .filter(ScrapeResult.scrape_run_id == scrape_run_id)
            .order_by(ScrapeResult.depth, ScrapeResult.id)
            .all()
        )

    def get_runs_for_website(self, website_id: int, limit: int = 20) -> list[ScrapeRunResponse]:
        """Return aggregated run summaries for a website, most-recent first."""
        rows = (
            self.db.query(
                ScrapeResult.scrape_run_id,
                ScrapeResult.website_id,
                sa_func.min(ScrapeResult.scraped_at).label("scraped_at"),
                sa_func.count(ScrapeResult.id).label("total_pages"),
                sa_func.sum(case((ScrapeResult.status == ScrapeResultStatus.SUCCESS, 1), else_=0)).label("success_count"),
                sa_func.sum(case((ScrapeResult.status == ScrapeResultStatus.ERROR, 1), else_=0)).label("error_count"),
            )
            .filter(ScrapeResult.website_id == website_id, ScrapeResult.scrape_run_id.isnot(None))
            .group_by(ScrapeResult.scrape_run_id, ScrapeResult.website_id)
            .order_by(sa_func.min(ScrapeResult.scraped_at).desc())
            .limit(limit)
            .all()
        )
        return [
            ScrapeRunResponse(
                scrape_run_id=r.scrape_run_id,
                website_id=r.website_id,
                scraped_at=r.scraped_at,
                total_pages=r.total_pages,
                success_count=r.success_count,
                error_count=r.error_count,
            )
            for r in rows
        ]
