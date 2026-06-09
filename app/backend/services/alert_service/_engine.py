"""Alert engine — orchestrates rule evaluation, de-dupe, and dispatch to sinks."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.backend.database import SessionLocal
from app.backend.database.models import Alert
from app.backend.services.alert_service._rules import RULES, get_rule_by_name
from app.backend.services.alert_service._sinks import format_telegram_message, persist_in_app, send_telegram
from app.backend.services.alert_service._types import AlertCandidate

logger = logging.getLogger(__name__)

_DEDUP_DAYS: int = 3


@dataclass
class RunResult:
    """Aggregate outcome of an alert-engine run."""
    candidates_evaluated: int = 0
    created_alerts: list[Alert] = field(default_factory=list)


def _is_duplicate(rule_type: str, ticker: str) -> bool:
    """Return True if an alert for (rule_type, ticker) was created within the dedup window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_DEDUP_DAYS)
    db = SessionLocal()
    try:
        existing = (
            db.query(Alert)
            .filter(
                Alert.rule_type == rule_type,
                Alert.ticker == ticker,
                Alert.created_at >= cutoff,
            )
            .first()
        )
        return existing is not None
    finally:
        db.close()


async def _dispatch_candidate(
    candidate: AlertCandidate,
    bot_token: str,
    chat_id: str,
    telegram_enabled: bool,
) -> Alert | None:
    """De-dupe one candidate and dispatch to Telegram + in-app sinks.

    Returns the persisted Alert, or None if suppressed by de-dupe.
    """
    if _is_duplicate(candidate.rule_type, candidate.ticker):
        logger.debug("Skipping duplicate alert: %s/%s", candidate.rule_type, candidate.ticker)
        return None

    sent = False
    tg_error: str | None = None
    if telegram_enabled and bot_token and chat_id:
        sent, tg_error = await send_telegram(
            bot_token, chat_id, format_telegram_message(candidate)
        )
        if not sent:
            logger.warning("Telegram send failed for %s: %s", candidate.ticker, tg_error)

    return persist_in_app(candidate, sent_to_telegram=sent, telegram_error=tg_error)


async def run_all_rules(settings: dict) -> RunResult:
    """Evaluate every registered rule, de-dupe, dispatch to sinks."""
    bot_token: str = settings.get("telegram_bot_token") or ""
    chat_id: str = settings.get("telegram_chat_id") or ""
    telegram_enabled: bool = bool(settings.get("telegram_enabled", False))

    result = RunResult()

    for rule_type, evaluator, threshold_extractor in RULES:
        try:
            thresholds = threshold_extractor(settings)
            candidates = await evaluator(thresholds)
        except Exception as exc:
            logger.exception("Rule %s evaluation failed: %s", rule_type, exc)
            continue

        result.candidates_evaluated += len(candidates)

        for c in candidates:
            alert = await _dispatch_candidate(c, bot_token, chat_id, telegram_enabled)
            if alert is not None:
                result.created_alerts.append(alert)

    return result


async def run_one_rule(rule_type: str, settings: dict) -> list[Alert]:
    """Run a single named rule on demand (immediate-trigger / scheduler-bypass path).

    Used by ``discovery_service.get_ideas`` to fire the ``high_confluence``
    rule the moment a 4+ signal stack is detected, without waiting for the
    next AlertScheduler tick.

    Args:
        rule_type: Name of a rule registered in ``RULES``.
        settings: Loaded alert settings dict (Telegram credentials + thresholds).

    Returns:
        List of Alert rows created. Empty if rule unknown, evaluator failed,
        or all candidates were suppressed by de-dupe.
    """
    entry = get_rule_by_name(rule_type)
    if entry is None:
        logger.warning("run_one_rule: unknown rule_type '%s'", rule_type)
        return []

    _, evaluator, threshold_extractor = entry
    bot_token: str = settings.get("telegram_bot_token") or ""
    chat_id: str = settings.get("telegram_chat_id") or ""
    telegram_enabled: bool = bool(settings.get("telegram_enabled", False))

    try:
        thresholds = threshold_extractor(settings)
        candidates = await evaluator(thresholds)
    except Exception as exc:
        logger.exception("run_one_rule(%s): evaluator failed: %s", rule_type, exc)
        return []

    created: list[Alert] = []
    for c in candidates:
        alert = await _dispatch_candidate(c, bot_token, chat_id, telegram_enabled)
        if alert is not None:
            created.append(alert)
    return created
