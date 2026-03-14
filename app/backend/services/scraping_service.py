"""Scraping service: Crawl4AI integration with concurrency limiting, timeout, content truncation, and data retention."""
import asyncio
import logging
from datetime import datetime, timezone

from crawl4ai import AsyncWebCrawler

from app.backend.database.connection import SessionLocal
from app.backend.models.schemas import ScrapeResultStatus, ScrapeStatus
from app.backend.repositories.scraping_repository import ScrapingRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONTENT_LENGTH: int = 1_048_576  # 1 MB – stored content truncation limit
MAX_RESULTS_PER_WEBSITE: int = 50  # data retention: keep only most recent N results
SCRAPE_TIMEOUT_SECONDS: int = 30  # asyncio.wait_for timeout for Crawl4AI arun()
MAX_CONCURRENT_SCRAPES: int = 3  # semaphore limit for concurrent scrapes

# Module-level semaphore shared by the scheduler and on-demand triggers
_scrape_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def execute_scrape(website_id: int) -> None:
    """Scrape a website and persist the result.

    This function:
    1. Acquires the shared semaphore (max MAX_CONCURRENT_SCRAPES concurrent scrapes).
    2. Opens its own DB session in a ``try/finally`` block guaranteeing ``session.close()``.
    3. Fetches the website; skips if not found or already ``in_progress``.
    4. Wraps ``AsyncWebCrawler.arun()`` in ``asyncio.wait_for`` with a 30-second timeout.
    5. Truncates content to ``MAX_CONTENT_LENGTH`` bytes while storing the original size.
    6. Saves a ``ScrapeResult`` and updates website status accordingly.
    7. Runs ``cleanup_old_results`` to enforce the per-website retention limit.

    Args:
        website_id: Primary key of the website to scrape.
    """
    async with _scrape_semaphore:
        session = SessionLocal()
        try:
            repo = ScrapingRepository(session)
            website = repo.get_website_by_id(website_id)
            if website is None:
                logger.warning("execute_scrape: website %d not found; skipping", website_id)
                return

            if website.scrape_status == ScrapeStatus.IN_PROGRESS:
                logger.info("execute_scrape: website %d already in_progress; skipping", website_id)
                return

            repo.update_website_status(website_id, ScrapeStatus.IN_PROGRESS)
            logger.info("execute_scrape: starting scrape for website %d (%s)", website_id, website.url)

            content: str | None = None
            content_length: int = 0
            error_message: str | None = None
            success: bool = False

            try:
                async with AsyncWebCrawler() as crawler:
                    result = await asyncio.wait_for(
                        crawler.arun(url=website.url),
                        timeout=SCRAPE_TIMEOUT_SECONDS,
                    )
                raw_content: str | None = result.markdown
                original_length: int = len(raw_content.encode("utf-8")) if raw_content else 0
                content_length = original_length
                if raw_content and original_length > MAX_CONTENT_LENGTH:
                    raw_content = raw_content[:MAX_CONTENT_LENGTH]
                    logger.info(
                        "execute_scrape: truncated content for website %d from %d to %d bytes",
                        website_id,
                        original_length,
                        MAX_CONTENT_LENGTH,
                    )
                content = raw_content
                success = True
                logger.info("execute_scrape: website %d scraped successfully (%d bytes)", website_id, content_length)
            except asyncio.TimeoutError:
                error_message = f"Scrape timed out after {SCRAPE_TIMEOUT_SECONDS} seconds"
                logger.error("execute_scrape: timeout for website %d", website_id)
            except Exception as exc:
                error_message = str(exc)
                logger.error("execute_scrape: error for website %d: %s", website_id, exc)

            if success:
                repo.create_scrape_result(
                    website_id=website_id,
                    content=content,
                    content_length=content_length,
                    status=ScrapeResultStatus.SUCCESS,
                )
                repo.update_website_status(
                    website_id,
                    ScrapeStatus.IDLE,
                    last_scraped_at=datetime.now(timezone.utc),
                )
                repo.cleanup_old_results(website_id, keep=MAX_RESULTS_PER_WEBSITE)
            else:
                repo.create_scrape_result(
                    website_id=website_id,
                    content=None,
                    content_length=0,
                    status=ScrapeResultStatus.ERROR,
                    error_message=error_message,
                )
                repo.update_website_status(
                    website_id,
                    ScrapeStatus.ERROR,
                    last_error=error_message,
                )
        finally:
            session.close()
