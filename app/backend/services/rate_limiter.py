"""Simple in-memory rate limiter for analysis endpoints."""

import os
import time
from collections import defaultdict

_STANDARD_MAX_TICKERS = 10
_DEEP_DIVE_MAX_TICKERS = 5


def _standard_daily_limit() -> int:
    return int(os.environ.get("STANDARD_DAILY_LIMIT", "10"))


def _deep_dive_daily_limit() -> int:
    return int(os.environ.get("DEEP_DIVE_DAILY_LIMIT", "5"))


def _deep_dive_enabled() -> bool:
    return os.environ.get("DEEP_DIVE_ENABLED", "false").lower() == "true"


_usage: dict[str, list[float]] = defaultdict(list)
_DAY_SECONDS = 86400


def _cleanup(key: str):
    cutoff = time.time() - _DAY_SECONDS
    _usage[key] = [t for t in _usage[key] if t > cutoff]


def check_analysis_allowed(mode: str, ticker_count: int = 0) -> tuple[bool, str]:
    """Check if analysis mode is allowed. Returns (allowed, reason)."""
    if mode == "deep_dive":
        if not _deep_dive_enabled():
            return False, "Deep Dive analysis is not enabled. Set DEEP_DIVE_ENABLED=true to activate."

        if ticker_count > _DEEP_DIVE_MAX_TICKERS:
            return False, f"Deep Dive is limited to {_DEEP_DIVE_MAX_TICKERS} tickers per run. Please select fewer tickers."

        key = "deep_dive_global"
        _cleanup(key)
        limit = _deep_dive_daily_limit()
        if len(_usage[key]) >= limit:
            return False, f"Deep Dive daily limit reached ({limit} runs/day). Try again tomorrow or use Standard mode."

    if mode == "standard":
        if ticker_count > _STANDARD_MAX_TICKERS:
            return False, f"Standard analysis is limited to {_STANDARD_MAX_TICKERS} tickers per run. Please select fewer tickers."

        key = "standard_global"
        _cleanup(key)
        limit = _standard_daily_limit()
        if len(_usage[key]) >= limit:
            return False, f"Standard analysis limit reached ({limit}/day). Try again tomorrow or use Quick Scan."

    return True, ""


def record_analysis(mode: str):
    """Record that an analysis was started."""
    if mode in ("standard", "deep_dive"):
        key = f"{mode}_global"
        _usage[key].append(time.time())


def get_usage_stats() -> dict:
    """Get current usage stats for display."""
    _cleanup("standard_global")
    _cleanup("deep_dive_global")
    return {
        "standard_used_today": len(_usage["standard_global"]),
        "standard_daily_limit": _standard_daily_limit(),
        "standard_max_tickers": _STANDARD_MAX_TICKERS,
        "deep_dive_enabled": _deep_dive_enabled(),
        "deep_dive_used_today": len(_usage["deep_dive_global"]),
        "deep_dive_daily_limit": _deep_dive_daily_limit(),
        "deep_dive_max_tickers": _DEEP_DIVE_MAX_TICKERS,
    }
