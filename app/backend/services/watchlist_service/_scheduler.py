"""Scheduled batch sentiment analyzer for the watchlist.

Wakes every `watchlist.batch_interval_hours` (from AppSetting; default 24),
runs run_batch_analysis() across all watched tickers, persists snapshots.
"""

import asyncio
import logging

from app.backend.database import SessionLocal
from app.backend.database.models import AppSetting
from app.backend.services.watchlist_service import run_batch_analysis

logger = logging.getLogger(__name__)


def _get_interval_hours() -> int:
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == "watchlist.batch_interval_hours").first()
        if row and row.value:
            try:
                return max(1, int(float(row.value)))
            except (ValueError, TypeError):
                pass
    finally:
        db.close()
    return 24


class WatchlistBatchScheduler:
    """Asyncio task that re-runs sentiment analysis on watchlist on a schedule."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="watchlist-batch-scheduler")
        logger.info("WatchlistBatchScheduler started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except asyncio.TimeoutError:
            self._task.cancel()
        finally:
            self._task = None
            logger.info("WatchlistBatchScheduler stopped")

    async def _loop(self) -> None:
        # Initial wait so we don't kick off immediately on app startup
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=120.0)
            return
        except asyncio.TimeoutError:
            pass

        while not self._stop.is_set():
            interval_hours = _get_interval_hours()
            interval_seconds = max(60, interval_hours * 3600)

            try:
                logger.info("WatchlistBatchScheduler running batch...")
                result = await run_batch_analysis()
                logger.info(
                    "WatchlistBatchScheduler done: analyzed=%d succeeded=%d failed=%d",
                    result.analyzed, result.succeeded, result.failed,
                )
            except Exception as exc:
                logger.exception("WatchlistBatchScheduler batch failed: %s", exc)

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval_seconds)
                return
            except asyncio.TimeoutError:
                continue


_scheduler: WatchlistBatchScheduler | None = None


def get_scheduler() -> WatchlistBatchScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = WatchlistBatchScheduler()
    return _scheduler
