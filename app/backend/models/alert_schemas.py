"""Pydantic schemas for the alert framework (squeeze + future rule types)."""

from typing import Any

from pydantic import BaseModel


class AlertItem(BaseModel):
    id: int
    rule_type: str
    ticker: str
    title: str
    message: str
    payload: dict[str, Any] | None = None
    severity: str = "info"
    sent_to_telegram: bool = False
    telegram_error: str | None = None
    is_read: bool = False
    created_at: str  # ISO


class AlertListResponse(BaseModel):
    alerts: list[AlertItem]
    unread_count: int
    total: int


class ScanResponse(BaseModel):
    """Result of a manual or scheduled rule scan."""
    candidates_evaluated: int
    alerts_created: int
    alerts: list[AlertItem]


class AlertSettingsResponse(BaseModel):
    telegram_bot_token: str  # masked, e.g. "••••ABCD" or "" if unset
    telegram_chat_id: str
    telegram_enabled: bool
    scan_interval_hours: int
    squeeze_min_short_pct: float
    squeeze_min_days_to_cover: float
    squeeze_require_insider_buy: bool
    csuite_min_value: float


class AlertSettingsRequest(BaseModel):
    telegram_bot_token: str | None = None  # None = leave unchanged; "" = clear
    telegram_chat_id: str | None = None
    telegram_enabled: bool | None = None
    scan_interval_hours: int | None = None
    squeeze_min_short_pct: float | None = None
    squeeze_min_days_to_cover: float | None = None
    squeeze_require_insider_buy: bool | None = None
    csuite_min_value: float | None = None


class TelegramTestResponse(BaseModel):
    success: bool
    error: str | None = None
