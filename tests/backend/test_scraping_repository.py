"""Tests for ScrapingRepository CRUD, due-for-scrape queries, retention cleanup, and stuck-state recovery."""
import pytest
from datetime import datetime, timedelta, timezone

from app.backend.repositories.scraping_repository import ScrapingRepository
from app.backend.database.models import ScrapingWebsite, ScrapeResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_website(
    db_session,
    url: str = "https://example.com",
    name: str = "Example",
    scrape_interval_minutes: int | None = None,
    is_active: bool = True,
    scrape_status: str = "idle",
    last_scraped_at: datetime | None = None,
) -> ScrapingWebsite:
    """Insert a ScrapingWebsite directly and return it."""
    website = ScrapingWebsite(
        url=url,
        name=name,
        scrape_interval_minutes=scrape_interval_minutes,
        is_active=is_active,
        scrape_status=scrape_status,
        last_scraped_at=last_scraped_at,
    )
    db_session.add(website)
    db_session.commit()
    db_session.refresh(website)
    return website


def _make_result(
    db_session,
    website_id: int,
    status: str = "success",
    content: str = "scraped text",
    content_length: int = 11,
    scraped_at: datetime | None = None,
) -> ScrapeResult:
    """Insert a ScrapeResult directly and return it."""
    result = ScrapeResult(
        website_id=website_id,
        status=status,
        content=content,
        content_length=content_length,
        scraped_at=scraped_at or datetime.now(timezone.utc),
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    return result


# ---------------------------------------------------------------------------
# 2.1.1 – create_website persists to DB
# ---------------------------------------------------------------------------

def test_create_website_persists_to_db(db_session):
    repo = ScrapingRepository(db_session)
    website = repo.create_website(url="https://news.example.com", name="News Site")

    assert website.id is not None
    assert website.url == "https://news.example.com"
    assert website.name == "News Site"
    assert website.scrape_status == "idle"
    assert website.is_active is True


# ---------------------------------------------------------------------------
# 2.1.2 – get_all_websites returns only active websites
# ---------------------------------------------------------------------------

def test_get_all_websites_returns_active_only(db_session):
    repo = ScrapingRepository(db_session)
    _make_website(db_session, url="https://active.com", name="Active", is_active=True)
    _make_website(db_session, url="https://inactive.com", name="Inactive", is_active=False)

    websites = repo.get_all_websites()

    urls = [w.url for w in websites]
    assert "https://active.com" in urls
    assert "https://inactive.com" not in urls


# ---------------------------------------------------------------------------
# 2.1.3 – delete_website cascades to its results
# ---------------------------------------------------------------------------

def test_delete_website_cascades_to_results(db_session):
    repo = ScrapingRepository(db_session)
    website = _make_website(db_session, url="https://cascade.com", name="Cascade")
    _make_result(db_session, website_id=website.id)
    _make_result(db_session, website_id=website.id)

    deleted = repo.delete_website(website.id)

    assert deleted is True
    remaining_results = db_session.query(ScrapeResult).filter(ScrapeResult.website_id == website.id).all()
    assert remaining_results == []


# ---------------------------------------------------------------------------
# 2.1.4 – update_website_status transitions status correctly
# ---------------------------------------------------------------------------

def test_update_website_status_transitions(db_session):
    repo = ScrapingRepository(db_session)
    website = _make_website(db_session, url="https://status.com", name="Status")

    updated = repo.update_website_status(website.id, status="in_progress")

    assert updated is not None
    assert updated.scrape_status == "in_progress"


def test_update_website_status_sets_last_error(db_session):
    repo = ScrapingRepository(db_session)
    website = _make_website(db_session, url="https://error-site.com", name="Error Site")

    updated = repo.update_website_status(website.id, status="error", last_error="Timeout exceeded")

    assert updated is not None
    assert updated.scrape_status == "error"
    assert updated.last_error == "Timeout exceeded"


# ---------------------------------------------------------------------------
# 2.1.5 – get_results_for_website returns most-recent first, respects limit
# ---------------------------------------------------------------------------

def test_get_results_for_website_ordered_by_date(db_session):
    repo = ScrapingRepository(db_session)
    website = _make_website(db_session, url="https://results.com", name="Results")
    now = datetime.now(timezone.utc)

    for i in range(5):
        _make_result(db_session, website_id=website.id, scraped_at=now - timedelta(minutes=i))

    results = repo.get_results_for_website(website.id, limit=3)

    assert len(results) == 3
    # Verify descending order: each result scraped_at >= next
    for i in range(len(results) - 1):
        assert results[i].scraped_at >= results[i + 1].scraped_at


# ---------------------------------------------------------------------------
# 2.1.6 – get_websites_due_for_scrape correctness
# ---------------------------------------------------------------------------

def test_get_websites_due_for_scrape_returns_overdue(db_session):
    repo = ScrapingRepository(db_session)
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    _make_website(
        db_session,
        url="https://overdue.com",
        name="Overdue",
        scrape_interval_minutes=60,
        is_active=True,
        last_scraped_at=past_time,
    )

    due = repo.get_websites_due_for_scrape()

    assert any(w.url == "https://overdue.com" for w in due)


def test_get_websites_due_for_scrape_excludes_recent(db_session):
    repo = ScrapingRepository(db_session)
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    _make_website(
        db_session,
        url="https://recent.com",
        name="Recent",
        scrape_interval_minutes=60,
        is_active=True,
        last_scraped_at=recent_time,
    )

    due = repo.get_websites_due_for_scrape()

    assert not any(w.url == "https://recent.com" for w in due)


def test_get_websites_due_for_scrape_excludes_in_progress(db_session):
    repo = ScrapingRepository(db_session)
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    _make_website(
        db_session,
        url="https://inprogress-due.com",
        name="InProgress Due",
        scrape_interval_minutes=60,
        is_active=True,
        scrape_status="in_progress",
        last_scraped_at=past_time,
    )

    due = repo.get_websites_due_for_scrape()

    assert not any(w.url == "https://inprogress-due.com" for w in due)


def test_get_websites_due_for_scrape_includes_never_scraped(db_session):
    repo = ScrapingRepository(db_session)
    _make_website(
        db_session,
        url="https://never-scraped.com",
        name="Never Scraped",
        scrape_interval_minutes=30,
        is_active=True,
        last_scraped_at=None,
    )

    due = repo.get_websites_due_for_scrape()

    assert any(w.url == "https://never-scraped.com" for w in due)


def test_get_websites_due_for_scrape_excludes_no_interval(db_session):
    repo = ScrapingRepository(db_session)
    _make_website(
        db_session,
        url="https://no-interval.com",
        name="No Interval",
        scrape_interval_minutes=None,
        is_active=True,
    )

    due = repo.get_websites_due_for_scrape()

    assert not any(w.url == "https://no-interval.com" for w in due)


# ---------------------------------------------------------------------------
# 2.1.7 – cleanup_old_results keeps most-recent N
# ---------------------------------------------------------------------------

def test_cleanup_old_results_keeps_most_recent(db_session):
    repo = ScrapingRepository(db_session)
    website = _make_website(db_session, url="https://cleanup.com", name="Cleanup")
    now = datetime.now(timezone.utc)

    result_ids = []
    for i in range(60):
        r = _make_result(
            db_session,
            website_id=website.id,
            scraped_at=now - timedelta(minutes=i),
        )
        result_ids.append(r.id)

    repo.cleanup_old_results(website.id, keep=50)

    remaining = db_session.query(ScrapeResult).filter(ScrapeResult.website_id == website.id).all()
    assert len(remaining) == 50

    # The remaining 50 should be the most-recent ones (lowest timedelta = most recent)
    remaining_ids = {r.id for r in remaining}
    most_recent_ids = set(result_ids[:50])  # result_ids[0] is the most recent
    assert remaining_ids == most_recent_ids


# ---------------------------------------------------------------------------
# 2.1.8 – reset_stuck_in_progress resets only in_progress
# ---------------------------------------------------------------------------

def test_reset_stuck_in_progress(db_session):
    repo = ScrapingRepository(db_session)
    stuck1 = _make_website(db_session, url="https://stuck1.com", name="Stuck 1", scrape_status="in_progress")
    stuck2 = _make_website(db_session, url="https://stuck2.com", name="Stuck 2", scrape_status="in_progress")
    idle = _make_website(db_session, url="https://idle.com", name="Idle", scrape_status="idle")

    repo.reset_stuck_in_progress()

    db_session.refresh(stuck1)
    db_session.refresh(stuck2)
    db_session.refresh(idle)

    assert stuck1.scrape_status == "idle"
    assert stuck2.scrape_status == "idle"
    assert idle.scrape_status == "idle"  # unchanged


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

def test_get_website_by_id_returns_none_for_missing(db_session):
    repo = ScrapingRepository(db_session)
    result = repo.get_website_by_id(99999)
    assert result is None


def test_delete_website_returns_false_for_missing(db_session):
    repo = ScrapingRepository(db_session)
    deleted = repo.delete_website(99999)
    assert deleted is False


def test_update_website_partial_update(db_session):
    repo = ScrapingRepository(db_session)
    website = _make_website(db_session, url="https://patch.com", name="Original Name")

    updated = repo.update_website(website.id, name="Updated Name")

    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.url == "https://patch.com"  # unchanged


def test_create_scrape_result_persists(db_session):
    repo = ScrapingRepository(db_session)
    website = _make_website(db_session, url="https://scrape-result.com", name="Scrape Result")

    result = repo.create_scrape_result(
        website_id=website.id,
        content="some markdown",
        content_length=13,
        status="success",
        error_message=None,
    )

    assert result.id is not None
    assert result.website_id == website.id
    assert result.content == "some markdown"
    assert result.status == "success"
