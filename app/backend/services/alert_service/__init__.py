"""Public alert service API — settings, scan, list, mark-read, test-telegram."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.backend.database import SessionLocal
from app.backend.database.models import Alert, AppSetting
from app.backend.models.alert_schemas import (
    AlertItem,
    AlertListResponse,
    AlertSettingsRequest,
    AlertSettingsResponse,
    ScanResponse,
    TelegramTestResponse,
)
from app.backend.services.alert_service._engine import run_all_rules, run_one_rule
from app.backend.services.alert_service._sinks import send_telegram

logger = logging.getLogger(__name__)


_SETTING_PREFIX = "alerts."

_DEFAULTS: dict[str, Any] = {
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_enabled": False,
    "scan_interval_hours": 4,
    "squeeze_min_short_pct": 25.0,
    "squeeze_min_days_to_cover": 2.0,
    "squeeze_require_insider_buy": True,
    "csuite_min_value": 250_000.0,
}


def _key(name: str) -> str:
    return f"{_SETTING_PREFIX}{name}"


def _get_raw(db: Session, name: str) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == _key(name)).first()
    return row.value if row else None


def _set_raw(db: Session, name: str, value: str) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == _key(name)).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=_key(name), value=value))


def _coerce(name: str, raw: str | None) -> Any:
    default = _DEFAULTS[name]
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(float(raw))
        except (ValueError, TypeError):
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except (ValueError, TypeError):
            return default
    return raw


def _load_all_settings(db: Session) -> dict[str, Any]:
    return {name: _coerce(name, _get_raw(db, name)) for name in _DEFAULTS}


def load_settings_sync() -> dict[str, Any]:
    """Helper for non-DI contexts (e.g. scheduler)."""
    db = SessionLocal()
    try:
        return _load_all_settings(db)
    finally:
        db.close()


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "•" * len(token)
    return "•" * 8 + token[-4:]


def get_alert_settings(db: Session) -> AlertSettingsResponse:
    s = _load_all_settings(db)
    return AlertSettingsResponse(
        telegram_bot_token=_mask_token(s["telegram_bot_token"]),
        telegram_chat_id=s["telegram_chat_id"],
        telegram_enabled=s["telegram_enabled"],
        scan_interval_hours=s["scan_interval_hours"],
        squeeze_min_short_pct=s["squeeze_min_short_pct"],
        squeeze_min_days_to_cover=s["squeeze_min_days_to_cover"],
        squeeze_require_insider_buy=s["squeeze_require_insider_buy"],
        csuite_min_value=s["csuite_min_value"],
    )


def update_alert_settings(db: Session, req: AlertSettingsRequest) -> AlertSettingsResponse:
    # Telegram token: None = leave unchanged, "" = clear, otherwise set
    if req.telegram_bot_token is not None:
        _set_raw(db, "telegram_bot_token", req.telegram_bot_token)
    if req.telegram_chat_id is not None:
        _set_raw(db, "telegram_chat_id", req.telegram_chat_id)
    if req.telegram_enabled is not None:
        _set_raw(db, "telegram_enabled", "true" if req.telegram_enabled else "false")
    if req.scan_interval_hours is not None:
        _set_raw(db, "scan_interval_hours", str(max(1, int(req.scan_interval_hours))))
    if req.squeeze_min_short_pct is not None:
        _set_raw(db, "squeeze_min_short_pct", str(float(req.squeeze_min_short_pct)))
    if req.squeeze_min_days_to_cover is not None:
        _set_raw(db, "squeeze_min_days_to_cover", str(float(req.squeeze_min_days_to_cover)))
    if req.squeeze_require_insider_buy is not None:
        _set_raw(db, "squeeze_require_insider_buy", "true" if req.squeeze_require_insider_buy else "false")
    if req.csuite_min_value is not None:
        _set_raw(db, "csuite_min_value", str(float(req.csuite_min_value)))
    db.commit()
    return get_alert_settings(db)


async def test_telegram(db: Session) -> TelegramTestResponse:
    s = _load_all_settings(db)
    bot_token = s["telegram_bot_token"]
    chat_id = s["telegram_chat_id"]
    if not bot_token or not chat_id:
        return TelegramTestResponse(success=False, error="Telegram bot token or chat ID not configured")
    success, error = await send_telegram(
        bot_token,
        chat_id,
        "✅ Test message from AI Hedge Fund alerts. Your bot is configured correctly.",
    )
    return TelegramTestResponse(success=success, error=error)


def _alert_to_item(a: Alert) -> AlertItem:
    return AlertItem(
        id=a.id,
        rule_type=a.rule_type,
        ticker=a.ticker,
        title=a.title,
        message=a.message,
        payload=a.payload,
        severity=a.severity,
        sent_to_telegram=bool(a.sent_to_telegram),
        telegram_error=a.telegram_error,
        is_read=bool(a.is_read),
        created_at=a.created_at.isoformat() if isinstance(a.created_at, datetime) else str(a.created_at),
    )


def list_alerts(db: Session, limit: int, offset: int, unread_only: bool) -> AlertListResponse:
    base = db.query(Alert)
    if unread_only:
        base = base.filter(Alert.is_read == False)  # noqa: E712
    total = base.count()
    unread_count = db.query(Alert).filter(Alert.is_read == False).count()  # noqa: E712
    rows = (
        base.order_by(Alert.created_at.desc(), Alert.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return AlertListResponse(
        alerts=[_alert_to_item(r) for r in rows],
        unread_count=unread_count,
        total=total,
    )


def mark_alert_read(db: Session, alert_id: int) -> bool:
    row = db.query(Alert).filter(Alert.id == alert_id).first()
    if row is None:
        return False
    row.is_read = True
    db.commit()
    return True


def mark_all_read(db: Session) -> int:
    count = db.query(Alert).filter(Alert.is_read == False).update({"is_read": True})  # noqa: E712
    db.commit()
    return count


async def scan_now() -> ScanResponse:
    """Manual or scheduled scan: load settings, run all rules, dispatch."""
    settings = load_settings_sync()
    result = await run_all_rules(settings)
    return ScanResponse(
        candidates_evaluated=result.candidates_evaluated,
        alerts_created=len(result.created_alerts),
        alerts=[_alert_to_item(a) for a in result.created_alerts],
    )


async def trigger_rule_immediately(rule_type: str) -> int:
    """Run a single named rule on demand (bypasses the scheduler).

    Used by the Discovery service to fire ``high_confluence`` immediately when
    a 4+ signal stack is detected on a fresh compute, without waiting up to 4h
    for the next AlertScheduler tick.

    Args:
        rule_type: Name of a registered rule (see RULES registry).

    Returns:
        Count of Alert rows created (after de-dupe). Zero if rule unknown,
        no candidates qualified, or all were suppressed by de-dupe.
    """
    settings = load_settings_sync()
    created = await run_one_rule(rule_type, settings)
    return len(created)


__all__ = [
    "get_alert_settings",
    "update_alert_settings",
    "test_telegram",
    "list_alerts",
    "mark_alert_read",
    "mark_all_read",
    "scan_now",
    "trigger_rule_immediately",
    "load_settings_sync",
]
