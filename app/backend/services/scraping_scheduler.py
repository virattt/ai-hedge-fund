"""Scraping scheduler: periodic asyncio loop with stuck-state recovery on startup."""
import asyncio
import logging

from app.backend.database.connection import SessionLocal
from app.backend.repositories.scraping_repository import ScrapingRepository
from app.backend.services.scraping_service import execute_scrape

logger = logging.getLogger(__name__)

# Interval between scheduler checks (seconds)
SCHEDULER_CHECK_INTERVAL_SECONDS: int = 60


class ScrapingScheduler:
    """Manages the periodic scraping background loop.

    On :meth:`start`, resets any websites stuck in ``in_progress`` state
    (e.g. from a previous server crash), then launches an asyncio background
    task that checks for due scrapes every
    :data:`SCHEDULER_CHECK_INTERVAL_SECONDS` seconds.

    Call :meth:`stop` during FastAPI shutdown to cancel the task cleanly.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the scheduler.

        1. Recovers any websites stuck in ``in_progress`` state.
        2. Launches the periodic check loop as a background asyncio task.
        """
        logger.info("ScrapingScheduler: starting")
        await self._recover_stuck_states()
        self._task = asyncio.create_task(self._loop(), name="scraping-scheduler")
        logger.info("ScrapingScheduler: background loop started")

    async def stop(self) -> None:
        """Cancel the background loop task and wait for it to finish."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("ScrapingScheduler: background loop stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _recover_stuck_states(self) -> None:
        """Reset websites stuck in ``in_progress`` to ``idle``.

        Called once on startup to handle cases where the server crashed while
        a scrape was running.  Opens its own DB session and closes it in a
        ``finally`` block.
        """
        session = SessionLocal()
        try:
            repo = ScrapingRepository(session)
            count = repo.reset_stuck_in_progress()
            if count:
                logger.warning(
                    "ScrapingScheduler: recovered %d website(s) stuck in 'in_progress'", count
                )
            else:
                logger.info("ScrapingScheduler: no stuck websites found on startup")
        finally:
            session.close()

    async def _check_and_run_due_scrapes(self) -> None:
        """Query for due websites and fire :func:`execute_scrape` for each.

        Opens its own DB session in a ``try/finally`` block.  Any exception
        (e.g. transient DB error) is caught and logged so the loop survives.
        """
        session = SessionLocal()
        try:
            repo = ScrapingRepository(session)
            due = repo.get_websites_due_for_scrape()
            if due:
                logger.info(
                    "ScrapingScheduler: %d website(s) due for scrape", len(due)
                )
            for website in due:
                logger.debug(
                    "ScrapingScheduler: dispatching scrape for website %d",
                    website.id,
                )
                scrape_task: asyncio.Task[None] = asyncio.create_task(
                    execute_scrape(website.id), name=f"scrape-{website.id}"
                )
                # Prevent silent discard of scrape errors by attaching a done-callback
                scrape_task.add_done_callback(_log_scrape_task_result)
        except Exception:
            logger.exception("ScrapingScheduler: error during due-scrape check; will retry next interval")
        finally:
            session.close()

    async def _loop(self) -> None:
        """Infinite loop: check for due scrapes, then sleep for the interval.

        Transient errors inside :meth:`_check_and_run_due_scrapes` are handled
        there.  :exc:`asyncio.CancelledError` propagates normally so
        :meth:`stop` works correctly.
        """
        logger.info(
            "ScrapingScheduler: entering loop (interval=%ds)", SCHEDULER_CHECK_INTERVAL_SECONDS
        )
        while True:
            await self._check_and_run_due_scrapes()
            await asyncio.sleep(SCHEDULER_CHECK_INTERVAL_SECONDS)


def _log_scrape_task_result(task: asyncio.Task[None]) -> None:
    """Done-callback that logs unhandled exceptions from fire-and-forget scrape tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "ScrapingScheduler: unhandled exception in scrape task '%s': %s",
            task.get_name(),
            exc,
        )
