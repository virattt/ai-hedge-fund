"""Tests for ScrapingScheduler: stuck-state recovery, periodic scrape dispatch, and shutdown."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.backend.services.scraping_scheduler import ScrapingScheduler


# ---------------------------------------------------------------------------
# 4.1.1 - Stuck-state recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recover_stuck_states_resets_in_progress(db_session):
    """_recover_stuck_states resets in_progress websites back to idle."""
    from app.backend.repositories.scraping_repository import ScrapingRepository

    repo = ScrapingRepository(db_session)
    site1 = repo.create_website("https://example.com", "Site One", scrape_interval_minutes=60)
    site2 = repo.create_website("https://example.org", "Site Two", scrape_interval_minutes=60)
    # Force both to in_progress
    repo.update_website_status(site1.id, "in_progress")
    repo.update_website_status(site2.id, "in_progress")

    scheduler = ScrapingScheduler()
    with patch("app.backend.services.scraping_scheduler.SessionLocal", return_value=db_session):
        # Prevent session.close() from closing our shared test session
        db_session.close = MagicMock()
        await scheduler._recover_stuck_states()

    db_session.expire_all()
    recovered1 = repo.get_website_by_id(site1.id)
    recovered2 = repo.get_website_by_id(site2.id)
    assert recovered1 is not None and recovered1.scrape_status == "idle"
    assert recovered2 is not None and recovered2.scrape_status == "idle"


# ---------------------------------------------------------------------------
# 4.1.2 - Due scrapes are dispatched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_and_run_triggers_due_scrapes():
    """_check_and_run_due_scrapes fires execute_scrape for each due website."""
    mock_website_1 = MagicMock()
    mock_website_1.id = 101
    mock_website_2 = MagicMock()
    mock_website_2.id = 202

    mock_repo = MagicMock()
    mock_repo.get_websites_due_for_scrape.return_value = [mock_website_1, mock_website_2]

    mock_session = MagicMock()

    with (
        patch("app.backend.services.scraping_scheduler.SessionLocal", return_value=mock_session),
        patch("app.backend.services.scraping_scheduler.ScrapingRepository", return_value=mock_repo),
        patch("app.backend.services.scraping_scheduler.execute_scrape", new_callable=AsyncMock) as mock_execute,
    ):
        scheduler = ScrapingScheduler()
        await scheduler._check_and_run_due_scrapes()

    assert mock_execute.call_count == 2
    called_ids = {call.args[0] for call in mock_execute.call_args_list}
    assert called_ids == {101, 202}


# ---------------------------------------------------------------------------
# 4.1.3 - No due scrapes → execute_scrape not called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_and_run_skips_when_none_due():
    """_check_and_run_due_scrapes does not call execute_scrape when list is empty."""
    mock_repo = MagicMock()
    mock_repo.get_websites_due_for_scrape.return_value = []

    mock_session = MagicMock()

    with (
        patch("app.backend.services.scraping_scheduler.SessionLocal", return_value=mock_session),
        patch("app.backend.services.scraping_scheduler.ScrapingRepository", return_value=mock_repo),
        patch("app.backend.services.scraping_scheduler.execute_scrape", new_callable=AsyncMock) as mock_execute,
    ):
        scheduler = ScrapingScheduler()
        await scheduler._check_and_run_due_scrapes()

    mock_execute.assert_not_called()


# ---------------------------------------------------------------------------
# 4.1.4 - stop() cancels the background task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_stop_cancels_task():
    """stop() cancels the asyncio task created by start()."""
    with (
        patch.object(ScrapingScheduler, "_recover_stuck_states", new_callable=AsyncMock),
        patch.object(ScrapingScheduler, "_loop", new_callable=AsyncMock),
    ):
        scheduler = ScrapingScheduler()
        await scheduler.start()
        assert scheduler._task is not None
        await scheduler.stop()
        assert scheduler._task.cancelled() or scheduler._task.done()


# ---------------------------------------------------------------------------
# 4.1.5 - Loop survives transient repository errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_and_run_handles_exception_gracefully():
    """_check_and_run_due_scrapes swallows repository errors without propagating."""
    mock_session = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_websites_due_for_scrape.side_effect = RuntimeError("DB unavailable")

    with (
        patch("app.backend.services.scraping_scheduler.SessionLocal", return_value=mock_session),
        patch("app.backend.services.scraping_scheduler.ScrapingRepository", return_value=mock_repo),
    ):
        scheduler = ScrapingScheduler()
        # Must not raise
        await scheduler._check_and_run_due_scrapes()
