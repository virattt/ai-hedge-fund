"""Helpers a CLI or future daemon can wrap around ``run_cycle``.

Nothing here talks to a broker or a data vendor. The wrapper records what
the cycle was asked to do, how it finished, and (on failure) a short
summary suitable for a heartbeat file or a webhook. Payloads stay free of
credentials: fund name, as-of date, a universe summary, status, and an
error type/message when the tick failed.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from hedge_fund.paths import default_events_path, default_heartbeat_path
from hedge_fund.pipeline.models import CycleRecord
from hedge_fund.pipeline.run_cycle import run_cycle

logger = logging.getLogger(__name__)

CYCLE_START = "cycle_start"
CYCLE_END = "cycle_end"
CYCLE_ERROR = "cycle_error"

EVENTS_PATH_ENV = "HEDGE_FUND_EVENTS_PATH"
HEARTBEAT_ENV = "HEDGE_FUND_HEARTBEAT"
HEARTBEAT_PATH_ENV = "HEDGE_FUND_HEARTBEAT_PATH"
WEBHOOK_URL_ENV = "HEDGE_FUND_WEBHOOK_URL"
WEBHOOK_TIMEOUT_ENV = "HEDGE_FUND_WEBHOOK_TIMEOUT"

DEFAULT_WEBHOOK_TIMEOUT = 5.0
_UNIVERSE_TICKER_CAP = 32
_ERROR_MESSAGE_CAP = 500
_TRUTHY = {"1", "true", "yes", "on"}
_DEFAULT_SENTINEL = "default"

# Values after these labels are stripped so a stray key in an exception
# message does not land in JSONL, the heartbeat, or a webhook body.
_SECRET_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|authorization|bearer)\b(\s*[:=]\s*)(\S+)"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.isoformat()


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in _TRUTHY


def _fund_name(fund: Any) -> str:
    spec = getattr(fund, "spec", None)
    name = getattr(spec, "name", None) or getattr(fund, "name", None)
    return str(name) if name else "unknown"


def universe_summary(universe: list[str] | None) -> dict[str, Any]:
    """Count + a short ticker list — enough to see what the tick covered."""
    names = [str(t) for t in (universe or [])]
    return {
        "n": len(names),
        "tickers": names[:_UNIVERSE_TICKER_CAP],
        "truncated": len(names) > _UNIVERSE_TICKER_CAP,
    }


def safe_error_message(exc: BaseException) -> str:
    """Exception text with obvious secret-shaped values redacted."""
    text = _SECRET_VALUE.sub(r"\1\2[redacted]", str(exc))
    if len(text) > _ERROR_MESSAGE_CAP:
        return text[:_ERROR_MESSAGE_CAP] + "…"
    return text


def _resolve_path(explicit: str | Path | None, env_name: str, default: Path) -> Path | None:
    """CLI/arg wins; else the env var; ``default`` means the user-dir path."""
    if explicit is not None:
        value = explicit if isinstance(explicit, str) else str(explicit)
        if value.strip().lower() in {"", _DEFAULT_SENTINEL}:
            return default
        return Path(value).expanduser()
    env = os.environ.get(env_name)
    if env is not None and env.strip():
        return Path(env.strip()).expanduser()
    return None


def _resolve_heartbeat_path(explicit: str | Path | None) -> Path | None:
    path = _resolve_path(explicit, HEARTBEAT_PATH_ENV, default_heartbeat_path())
    if path is not None:
        return path
    if _truthy(os.environ.get(HEARTBEAT_ENV)):
        return default_heartbeat_path()
    return None


def _resolve_webhook_url(explicit: str | None) -> str | None:
    if explicit is not None:
        url = explicit.strip()
        return url or None
    url = (os.environ.get(WEBHOOK_URL_ENV) or "").strip()
    return url or None


def _resolve_webhook_timeout(explicit: float | None) -> float:
    if explicit is not None:
        if explicit <= 0:
            raise ValueError(f"{WEBHOOK_TIMEOUT_ENV} must be positive, got {explicit}")
        return float(explicit)
    raw = os.environ.get(WEBHOOK_TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_WEBHOOK_TIMEOUT
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(
            f"{WEBHOOK_TIMEOUT_ENV} must be a positive number of seconds, got {raw!r}"
        ) from exc
    if value <= 0:
        raise ValueError(f"{WEBHOOK_TIMEOUT_ENV} must be positive, got {raw!r}")
    return value


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except OSError:
        logger.exception("could not append cycle event to %s", path)


def _read_heartbeat(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_heartbeat(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError:
        logger.exception("could not write heartbeat file %s", path)


def _log_event(event: str, payload: dict[str, Any]) -> None:
    fund = payload.get("fund")
    as_of = payload.get("as_of")
    n = (payload.get("universe") or {}).get("n")
    if event == CYCLE_ERROR:
        logger.error(
            "%s fund=%s as_of=%s universe=%s status=%s error_type=%s error=%s",
            event, fund, as_of, n, payload.get("status"),
            payload.get("error_type"), payload.get("error_message"),
        )
        return
    extra = ""
    if event == CYCLE_END:
        extra = f" nav={payload.get('nav')} orders={payload.get('n_orders')}"
    logger.info(
        "%s fund=%s as_of=%s universe=%s status=%s%s",
        event, fund, as_of, n, payload.get("status"), extra,
    )


class CycleObserver:
    """Emit cycle events, refresh a heartbeat file, POST on failure.

    Construct with explicit paths/URL, or ``from_env()`` so a daemon and
    the CLI share one configuration story.
    """

    def __init__(
        self,
        *,
        events_path: Path | None = None,
        heartbeat_path: Path | None = None,
        webhook_url: str | None = None,
        webhook_timeout: float = DEFAULT_WEBHOOK_TIMEOUT,
    ) -> None:
        self.events_path = events_path
        self.heartbeat_path = heartbeat_path
        self.webhook_url = webhook_url
        self.webhook_timeout = webhook_timeout

    @classmethod
    def from_env(
        cls,
        *,
        events_path: str | Path | None = None,
        heartbeat_path: str | Path | None = None,
        webhook_url: str | None = None,
        webhook_timeout: float | None = None,
    ) -> CycleObserver:
        """Build from CLI arguments, falling back to ``HEDGE_FUND_*`` env vars."""
        return cls(
            events_path=_resolve_path(events_path, EVENTS_PATH_ENV, default_events_path()),
            heartbeat_path=_resolve_heartbeat_path(heartbeat_path),
            webhook_url=_resolve_webhook_url(webhook_url),
            webhook_timeout=_resolve_webhook_timeout(webhook_timeout),
        )

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        body = dict(payload)
        body.setdefault("event", event)
        body.setdefault("ts", _iso(_utc_now()))
        _log_event(event, body)
        if self.events_path is not None:
            _append_jsonl(self.events_path, body)

    def write_heartbeat(self, fields: dict[str, Any]) -> None:
        if self.heartbeat_path is None:
            return
        previous = _read_heartbeat(self.heartbeat_path)
        payload = {
            "status": fields.get("status"),
            "fund": fields.get("fund"),
            "as_of": fields.get("as_of"),
            "updated_at": fields.get("ts") or _iso(_utc_now()),
            "last_success_at": previous.get("last_success_at"),
            "last_failure_at": previous.get("last_failure_at"),
            "last_as_of": previous.get("last_as_of"),
            "error_type": None,
            "error_message": None,
            "nav": previous.get("nav"),
        }
        status = fields.get("status")
        if status == "ok":
            payload["last_success_at"] = payload["updated_at"]
            payload["last_as_of"] = fields.get("as_of")
            payload["nav"] = fields.get("nav")
        elif status == "error":
            payload["last_failure_at"] = payload["updated_at"]
            payload["last_as_of"] = fields.get("as_of") or previous.get("last_as_of")
            payload["error_type"] = fields.get("error_type")
            payload["error_message"] = fields.get("error_message")
        elif status == "running":
            payload["error_type"] = None
            payload["error_message"] = None
        _write_heartbeat(self.heartbeat_path, payload)

    def notify_failure(self, payload: dict[str, Any]) -> None:
        """POST *payload* to the configured webhook. Never raises."""
        if not self.webhook_url:
            return
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.webhook_timeout,
                headers={"Content-Type": "application/json", "User-Agent": "aihf-observability"},
            )
            response.raise_for_status()
        except Exception:
            logger.exception("cycle failure webhook failed; original cycle error is unchanged")

    def observe(
        self,
        fund: Any,
        as_of: str,
        broker: Any,
        data_client: Any,
        universe: list[str],
        *,
        run_cycle_fn: Callable[..., CycleRecord] | None = None,
    ) -> CycleRecord:
        """Run one cycle under this observer. Re-raises whatever the cycle raises."""
        cycle = run_cycle_fn or run_cycle
        fund_name = _fund_name(fund)
        summary = universe_summary(universe)
        started = _iso(_utc_now())
        start_payload = {
            "event": CYCLE_START,
            "ts": started,
            "fund": fund_name,
            "as_of": as_of,
            "universe": summary,
            "status": "running",
        }
        self.emit(CYCLE_START, start_payload)
        self.write_heartbeat(start_payload)
        try:
            record = cycle(fund, as_of, broker, data_client, universe)
        except Exception as exc:
            failed = _iso(_utc_now())
            error_payload = {
                "event": CYCLE_ERROR,
                "ts": failed,
                "fund": fund_name,
                "as_of": as_of,
                "universe": summary,
                "status": "error",
                "error_type": type(exc).__name__,
                "error_message": safe_error_message(exc),
            }
            self.emit(CYCLE_ERROR, error_payload)
            self.write_heartbeat(error_payload)
            self.notify_failure(error_payload)
            raise
        ended = _iso(_utc_now())
        end_payload = {
            "event": CYCLE_END,
            "ts": ended,
            "fund": record.fund,
            "as_of": record.as_of,
            "universe": universe_summary(record.universe),
            "status": "ok",
            "nav": record.nav,
            "n_orders": len(record.orders),
            "n_fills": len(record.fills),
            "n_skipped": len(record.skipped),
            "n_clamps": len(record.clamps),
        }
        self.emit(CYCLE_END, end_payload)
        self.write_heartbeat(end_payload)
        return record


def observe_cycle(
    fund: Any,
    as_of: str,
    broker: Any,
    data_client: Any,
    universe: list[str],
    *,
    observer: CycleObserver | None = None,
    run_cycle_fn: Callable[..., CycleRecord] | None = None,
    events_path: str | Path | None = None,
    heartbeat_path: str | Path | None = None,
    webhook_url: str | None = None,
) -> CycleRecord:
    """Run ``run_cycle`` (or *run_cycle_fn*) with events / heartbeat / webhook.

    When *observer* is omitted, configuration comes from the keyword paths
    and ``HEDGE_FUND_*`` environment variables. Logging always happens.
    """
    obs = observer or CycleObserver.from_env(
        events_path=events_path,
        heartbeat_path=heartbeat_path,
        webhook_url=webhook_url,
    )
    return obs.observe(
        fund, as_of, broker, data_client, universe, run_cycle_fn=run_cycle_fn,
    )
