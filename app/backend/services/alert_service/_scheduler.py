"""Background scheduler that periodically runs all alert rules."""

import asyncio
import logging

from app.backend.services.alert_service import load_settings_sync, scan_now

logger = logging.getLogger(__name__)


class AlertScheduler:
    """Asyncio task that wakes up every `scan_interval_hours` and runs alerts."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="alert-scheduler")
        logger.info("AlertScheduler started")

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
            logger.info("AlertScheduler stopped")

    async def _loop(self) -> None:
        # Initial wait so we don't scan immediately on app start (gives services time to warm)
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=60.0)
            return  # stop was set during initial wait
        except asyncio.TimeoutError:
            pass

        while not self._stop.is_set():
            try:
                interval_hours = int(load_settings_sync().get("scan_interval_hours") or 4)
            except Exception:
                interval_hours = 4
            interval_seconds = max(60, interval_hours * 3600)

            try:
                logger.info("AlertScheduler running rule scan...")
                result = await scan_now()
                logger.info(
                    "AlertScheduler scan complete: %d candidates, %d alerts created",
                    result.candidates_evaluated,
                    result.alerts_created,
                )
            except Exception as exc:
                logger.exception("AlertScheduler scan failed: %s", exc)

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval_seconds)
                return  # stop signal
            except asyncio.TimeoutError:
                continue


_scheduler: AlertScheduler | None = None


def get_scheduler() -> AlertScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AlertScheduler()
    return _scheduler
