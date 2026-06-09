"""Alert rule registry — add new rules by importing and listing them in RULES."""

from collections.abc import Awaitable, Callable

from . import (
    analyst_upgrade,
    cluster_buy_rule,
    commodity_tailwind_rule,
    csuite_buy,
    earnings_sentiment_shift,
    high_confluence,
    insider_sell_cluster_rule,
    new_spinoff,
    score_movement,
    squeeze,
)
from app.backend.services.alert_service._types import AlertCandidate

RuleFn = Callable[[dict], Awaitable[list[AlertCandidate]]]


def _squeeze_thresholds_from_settings(settings: dict) -> dict:
    return {
        "min_short_pct": settings.get("squeeze_min_short_pct", 25.0),
        "min_days_to_cover": settings.get("squeeze_min_days_to_cover", 2.0),
        "require_insider_buy": settings.get("squeeze_require_insider_buy", True),
    }


def _new_spinoff_thresholds(_settings: dict) -> dict:
    return {}  # no configurable thresholds


def _csuite_thresholds(settings: dict) -> dict:
    return {"min_value": settings.get("csuite_min_value", 250_000.0)}


def _high_confluence_thresholds(settings: dict) -> dict:
    return {
        "min_sources": int(settings.get("high_confluence_min_sources", 4)),
        "min_score": float(settings.get("high_confluence_min_score", 80.0)),
    }


def _score_movement_thresholds(settings: dict) -> dict:
    return {
        "lookback_days": int(settings.get("score_movement_lookback_days", 7)),
        "min_abs_delta": float(settings.get("score_movement_min_abs_delta", 30.0)),
    }


# Each entry: (rule_type, evaluator function, thresholds extractor)
RULES: list[tuple[str, RuleFn, Callable[[dict], dict]]] = [
    ("squeeze", squeeze.evaluate, _squeeze_thresholds_from_settings),
    ("new_spinoff", new_spinoff.evaluate, _new_spinoff_thresholds),
    ("csuite_buy", csuite_buy.evaluate, _csuite_thresholds),
    ("earnings_sentiment_shift", earnings_sentiment_shift.evaluate, lambda _s: {}),
    ("cluster_buy", cluster_buy_rule.evaluate, lambda _s: {}),
    ("analyst_upgrade", analyst_upgrade.evaluate, lambda _s: {}),
    ("commodity_tailwind", commodity_tailwind_rule.evaluate, lambda _s: {}),
    ("score_movement", score_movement.evaluate, _score_movement_thresholds),
    ("high_confluence", high_confluence.evaluate, _high_confluence_thresholds),
    ("insider_sell_cluster", insider_sell_cluster_rule.evaluate, lambda _s: {}),
]


def get_rule_by_name(rule_type: str) -> tuple[str, RuleFn, Callable[[dict], dict]] | None:
    """Look up a rule entry by its rule_type. Used for immediate-trigger paths."""
    for entry in RULES:
        if entry[0] == rule_type:
            return entry
    return None
