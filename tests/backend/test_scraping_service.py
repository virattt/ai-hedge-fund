"""Tests for ScrapingService: Crawl4AI integration, timeout, content truncation, retention cleanup, and session management."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.backend.database.models import ScrapeResult, ScrapingWebsite


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_website(
    db_session,
    url: str = "https://example.com",
    name: str = "Example",
    scrape_status: str = "idle",
) -> ScrapingWebsite:
    """Insert a ScrapingWebsite into the in-memory DB and return it."""
    website = ScrapingWebsite(
        url=url,
        name=name,
        scrape_status=scrape_status,
        max_depth=1,
        max_pages=10,
        include_external=False,
    )
    db_session.add(website)
    db_session.commit()
    db_session.refresh(website)
    return website


def _fake_crawl_result(markdown: str, url: str = "https://example.com") -> MagicMock:
    """Return a mock Crawl4AI CrawlResult with .markdown, .url, .metadata set."""
    result = MagicMock()
    result.markdown = markdown
    result.success = True
    result.status_code = 200
    result.error_message = None
    result.url = url
    result.metadata = {"depth": 0}
    return result


# ---------------------------------------------------------------------------
# Helper: a fresh SessionLocal that returns db_session
# ---------------------------------------------------------------------------


def _session_factory(db_session):
    """Return a callable that always yields db_session (mimics SessionLocal)."""

    def factory() -> object:
        return db_session

    return factory


# ---------------------------------------------------------------------------
# Test: success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_scrape_saves_result_on_success(db_session):
    """execute_scrape() creates a success ScrapeResult and resets website status to idle."""
    import app.backend.services.scraping_service as svc_module

    website = _make_website(db_session)
    fake_result = _fake_crawl_result("# Hello world\n\nSome content.")

    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=fake_result)
    mock_crawler_ctx = AsyncMock()
    mock_crawler_ctx.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(svc_module, "SessionLocal", _session_factory(db_session)),
        patch("app.backend.services.scraping_service.AsyncWebCrawler", return_value=mock_crawler_ctx),
    ):
        await svc_module.execute_scrape(website.id)

    # Re-query from db_session; the original object was loaded in a separate service session
    updated = db_session.query(ScrapingWebsite).filter(ScrapingWebsite.id == website.id).first()
    results = db_session.query(ScrapeResult).filter(ScrapeResult.website_id == website.id).all()

    assert len(results) == 1
    assert results[0].status == "success"
    assert results[0].content == "# Hello world\n\nSome content."
    assert updated.scrape_status == "idle"
    assert updated.last_scraped_at is not None


# ---------------------------------------------------------------------------
# Test: timeout error path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_scrape_saves_error_on_timeout(db_session):
    """execute_scrape() stores an error result and sets website status to 'error' on timeout."""
    import app.backend.services.scraping_service as svc_module

    website = _make_website(db_session)

    async def hang(*args, **kwargs) -> None:
        await asyncio.sleep(9999)

    mock_crawler = AsyncMock()
    mock_crawler.arun = hang
    mock_crawler_ctx = AsyncMock()
    mock_crawler_ctx.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(svc_module, "SessionLocal", _session_factory(db_session)),
        patch("app.backend.services.scraping_service.AsyncWebCrawler", return_value=mock_crawler_ctx),
        # Patch the timeout constant so the test doesn't actually wait 30 seconds
        patch.object(svc_module, "SCRAPE_TIMEOUT_SECONDS", 0.01),
    ):
        await svc_module.execute_scrape(website.id)

    # Re-query from db_session; the original object was loaded in a separate service session
    updated = db_session.query(ScrapingWebsite).filter(ScrapingWebsite.id == website.id).first()
    results = db_session.query(ScrapeResult).filter(ScrapeResult.website_id == website.id).all()

    assert len(results) == 1
    assert results[0].status == "error"
    assert results[0].error_message is not None
    assert "timed out" in results[0].error_message.lower()
    assert updated.scrape_status == "error"


# ---------------------------------------------------------------------------
# Test: generic exception error path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_scrape_saves_error_on_exception(db_session):
    """execute_scrape() stores an error result and sets website status to 'error' on exception."""
    import app.backend.services.scraping_service as svc_module

    website = _make_website(db_session)

    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(side_effect=RuntimeError("network failure"))
    mock_crawler_ctx = AsyncMock()
    mock_crawler_ctx.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(svc_module, "SessionLocal", _session_factory(db_session)),
        patch("app.backend.services.scraping_service.AsyncWebCrawler", return_value=mock_crawler_ctx),
    ):
        await svc_module.execute_scrape(website.id)

    # Re-query from db_session; the original object was loaded in a separate service session
    updated = db_session.query(ScrapingWebsite).filter(ScrapingWebsite.id == website.id).first()
    results = db_session.query(ScrapeResult).filter(ScrapeResult.website_id == website.id).all()

    assert len(results) == 1
    assert results[0].status == "error"
    assert results[0].error_message is not None
    assert updated.scrape_status == "error"


# ---------------------------------------------------------------------------
# Test: skip if already in_progress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_scrape_skips_if_already_in_progress(db_session):
    """execute_scrape() still scrapes when status is in_progress (set by route before background task)."""
    import app.backend.services.scraping_service as svc_module

    website = _make_website(db_session, scrape_status="in_progress")

    fake_result = _fake_crawl_result("# In progress content")
    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=fake_result)
    mock_crawler_ctx = AsyncMock()
    mock_crawler_ctx.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(svc_module, "SessionLocal", _session_factory(db_session)),
        patch("app.backend.services.scraping_service.AsyncWebCrawler", return_value=mock_crawler_ctx),
    ):
        await svc_module.execute_scrape(website.id)

    # Scrape should have run and produced a result
    results = db_session.query(ScrapeResult).filter(ScrapeResult.website_id == website.id).all()
    assert len(results) == 1
    assert results[0].status == "success"
    mock_crawler.arun.assert_called_once()


# ---------------------------------------------------------------------------
# Test: content truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_scrape_truncates_large_content(db_session):
    """execute_scrape() truncates content exceeding MAX_CONTENT_LENGTH bytes."""
    import app.backend.services.scraping_service as svc_module

    website = _make_website(db_session)

    two_mb_content = "A" * (2 * 1024 * 1024)  # 2 MB of ASCII
    fake_result = _fake_crawl_result(two_mb_content)

    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=fake_result)
    mock_crawler_ctx = AsyncMock()
    mock_crawler_ctx.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(svc_module, "SessionLocal", _session_factory(db_session)),
        patch("app.backend.services.scraping_service.AsyncWebCrawler", return_value=mock_crawler_ctx),
    ):
        await svc_module.execute_scrape(website.id)

    results = db_session.query(ScrapeResult).filter(ScrapeResult.website_id == website.id).all()

    assert len(results) == 1
    assert results[0].status == "success"
    # Stored content must not exceed 1 MB
    assert len(results[0].content.encode("utf-8")) <= svc_module.MAX_CONTENT_LENGTH
    # content_length must reflect the original pre-truncation size
    assert results[0].content_length == len(two_mb_content.encode("utf-8"))


# ---------------------------------------------------------------------------
# Test: session closed on error (try/finally guarantee)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_scrape_session_closed_on_error(db_session):
    """The DB session is always closed even when Crawl4AI raises an exception."""
    import app.backend.services.scraping_service as svc_module

    website = _make_website(db_session)

    # Build a mock session that wraps db_session but tracks close() calls
    mock_session = MagicMock(wraps=db_session)
    mock_session_factory = MagicMock(return_value=mock_session)

    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(side_effect=ValueError("boom"))
    mock_crawler_ctx = AsyncMock()
    mock_crawler_ctx.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(svc_module, "SessionLocal", mock_session_factory),
        patch("app.backend.services.scraping_service.AsyncWebCrawler", return_value=mock_crawler_ctx),
    ):
        await svc_module.execute_scrape(website.id)

    mock_session.close.assert_called_once()
