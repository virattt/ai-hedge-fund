"""Alert sinks — Telegram + in-app DB persistence."""

import logging

import httpx

from app.backend.database import SessionLocal
from app.backend.database.models import Alert
from app.backend.services.alert_service._types import AlertCandidate

logger = logging.getLogger(__name__)


_TELEGRAM_BASE = "https://api.telegram.org/bot"


async def send_telegram(bot_token: str, chat_id: str, text: str) -> tuple[bool, str | None]:
    """Send a message via the Telegram bot API. Returns (success, error_message)."""
    if not bot_token or not chat_id:
        return False, "Telegram not configured"
    url = f"{_TELEGRAM_BASE}{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            })
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
            data = resp.json()
            if not data.get("ok"):
                return False, data.get("description") or "Telegram returned ok=false"
            return True, None
    except httpx.HTTPError as exc:
        return False, f"Network error: {exc}"
    except Exception as exc:
        return False, f"Unexpected error: {exc}"


def format_telegram_message(candidate: AlertCandidate) -> str:
    """Plain-text message body for Telegram (no markdown to avoid parsing issues)."""
    # high_confluence rule already includes 🚨 in its title; other rules get a
    # severity-driven emoji prefix.
    if candidate.rule_type == "high_confluence":
        return (
            "🚨🚨🚨 EMERGENCY ALPHA 🚨🚨🚨\n"
            f"{candidate.title}\n\n"
            f"{candidate.message}\n\n"
            "— SUPER-NOVA confluence detected —"
        )
    sev_emoji = {"info": "🔵", "warning": "🟡", "critical": "🔴"}.get(candidate.severity, "🔵")
    return f"{sev_emoji} {candidate.title}\n\n{candidate.message}"


def persist_in_app(
    candidate: AlertCandidate,
    sent_to_telegram: bool,
    telegram_error: str | None,
) -> Alert:
    """Write an Alert row to the DB."""
    db = SessionLocal()
    try:
        alert = Alert(
            rule_type=candidate.rule_type,
            ticker=candidate.ticker,
            title=candidate.title,
            message=candidate.message,
            payload=candidate.payload,
            severity=candidate.severity,
            sent_to_telegram=sent_to_telegram,
            telegram_error=telegram_error,
            is_read=False,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    finally:
        db.close()
