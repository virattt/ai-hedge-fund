"""
Scheduler: pre-market analysis, market-hours execution window, post-market
reconciliation, heartbeat monitoring, and error alerting.
Configurable via config file or dataclass. Uses APScheduler.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _HAS_APSCHEDULER = True
except ImportError:
    _HAS_APSCHEDULER = False
    BackgroundScheduler = None  # type: ignore
    CronTrigger = None


@dataclass
class ScheduleConfig:
    """Configurable schedule (ET assumed for market times)."""

    pre_market_time: str = "08:00"  # HH:MM
    market_open_time: str = "09:30"
    market_close_time: str = "16:00"
    post_market_time: str = "16:30"
    timezone: str = "America/New_York"
    heartbeat_interval_minutes: int = 15
    alert_webhook_url: str | None = None
    alert_email: str | None = None
    config_path: str | Path | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> "ScheduleConfig":
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p) as f:
            data = json.load(f)
        return cls(
            pre_market_time=data.get("pre_market_time", cls.pre_market_time),
            market_open_time=data.get("market_open_time", cls.market_open_time),
            market_close_time=data.get("market_close_time", cls.market_close_time),
            post_market_time=data.get("post_market_time", cls.post_market_time),
            timezone=data.get("timezone", cls.timezone),
            heartbeat_interval_minutes=data.get("heartbeat_interval_minutes", cls.heartbeat_interval_minutes),
            alert_webhook_url=data.get("alert_webhook_url"),
            alert_email=data.get("alert_email"),
            config_path=p,
        )


def _run_callback(
    name: str,
    callback: Callable[[], Any] | Callable[[], Awaitable[Any]],
    alert_webhook_url: str | None,
    alert_email: str | None,
) -> None:
    try:
        import asyncio
        result = callback()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
        logger.info("scheduler job %s completed", name)
    except Exception as e:
        logger.exception("scheduler job %s failed: %s", name, e)
        payload = {"job": name, "error": str(e)}
        if alert_webhook_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    alert_webhook_url,
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception as alert_err:
                logger.warning("alert webhook failed: %s", alert_err)
        if alert_email:
            logger.warning("email alert not implemented; set alert_webhook_url for alerts")


class TradingScheduler:
    """
    Runs pre-market analysis, execution-window tasks, and post-market reconciliation
    at configurable times. Heartbeat and error alerting via webhook/email.
    """

    def __init__(
        self,
        config: ScheduleConfig | None = None,
        pre_market_callback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None = None,
        execution_callback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None = None,
        post_market_callback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None = None,
        heartbeat_callback: Callable[[], Any] | None = None,
    ):
        if not _HAS_APSCHEDULER:
            raise RuntimeError("apscheduler is required: pip install apscheduler")
        self._config = config or ScheduleConfig()
        if self._config.config_path:
            self._config = ScheduleConfig.from_file(self._config.config_path)
        self._pre_market = pre_market_callback
        self._execution = execution_callback
        self._post_market = post_market_callback
        self._heartbeat = heartbeat_callback or (lambda: None)
        self._scheduler: Any = None

    def _job(self, name: str, callback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None) -> None:
        if callback is None:
            return
        _run_callback(
            name,
            callback,
            self._config.alert_webhook_url,
            self._config.alert_email,
        )

    def start(self) -> None:
        self._scheduler = BackgroundScheduler(timezone=self._config.timezone)
        # Pre-market
        if self._pre_market:
            hour, minute = self._config.pre_market_time.split(":")[:2]
            self._scheduler.add_job(
                lambda: self._job("pre_market", self._pre_market),
                CronTrigger(hour=int(hour), minute=int(minute),
                           timezone=self._config.timezone),
                id="pre_market",
            )
        # Execution window: run at market open (actual execution controlled by app)
        if self._execution:
            hour, minute = self._config.market_open_time.split(":")[:2]
            self._scheduler.add_job(
                lambda: self._job("execution", self._execution),
                CronTrigger(hour=int(hour), minute=int(minute),
                           timezone=self._config.timezone),
                id="execution",
            )
        # Post-market
        if self._post_market:
            hour, minute = self._config.post_market_time.split(":")[:2]
            self._scheduler.add_job(
                lambda: self._job("post_market", self._post_market),
                CronTrigger(hour=int(hour), minute=int(minute),
                           timezone=self._config.timezone),
                id="post_market",
            )
        # Heartbeat
        self._scheduler.add_job(
            lambda: self._job("heartbeat", self._heartbeat),
            CronTrigger(minute=f"*/{self._config.heartbeat_interval_minutes}",
                       timezone=self._config.timezone),
            id="heartbeat",
        )
        self._scheduler.start()
        logger.info("TradingScheduler started (pre_market=%s, post_market=%s)",
                    self._config.pre_market_time, self._config.post_market_time)

    def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        logger.info("TradingScheduler stopped")
