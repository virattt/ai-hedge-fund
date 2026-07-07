"""A-share valuation provider backed by Tushare pro ``daily_basic``.

Fills the valuation block (market_cap / pe / pb / ps) that akshare cannot
supply reliably: Eastmoney endpoints are persistently blocked and Sina carries
no market cap. Tushare's authenticated ``daily_basic`` is the stable source.

Token & degradation
-------------------
- Reads ``TUSHARE_TOKEN`` from the environment. Absent → this module is a
  no-op (every public call returns ``None``); the rest of the A-share layer
  falls back to its current behaviour.
- On a Tushare *permission / insufficient-points* error the module latches a
  process-wide breaker so we never re-fire the gated endpoint per ticker.
- Transient network errors are NOT breaker-worthy.

All public entry points return ``None`` on failure — they never raise.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

from src.data.cache import get_cache

logger = logging.getLogger(__name__)

_cache = get_cache()

# Per-trade_date memo of the full-market daily_basic table. One call covers
# every ticker for that date, so the concurrent fan-out shares it (guarded by
# the per-key lock in _cache.fetch_lock).
_daily_basic_tables: dict[str, pd.DataFrame] = {}

# Process-wide breaker: tripped on a Tushare permission error (insufficient
# points). Once tripped, get_valuation short-circuits for the rest of the run.
_disabled: bool = False

# Marks permission-style errors in Tushare exception text / error payloads.
_PERMISSION_TOKENS = (
    "权限", "permission", "积分", "40203", "40001", "40002", "40003",
)


def _get_pro() -> Any:
    """Return a cached ``tushare.pro_api`` client, or ``None`` if no token.

    Imports ``tushare`` lazily so this module loads even when the package or
    token is absent — US-only runs and token-less CI must not break.
    """
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        return None
    cached = getattr(_get_pro, "_pro", None)
    if cached is not None:
        return cached
    import tushare as ts  # lazy: keeps token-less envs dependency-light

    ts.set_token(token)
    client = ts.pro_api()
    _get_pro._pro = client  # type: ignore[attr-defined]
    return client


def _to_float(v) -> float | None:
    """Coerce to float, treating NaN / None / garbage as None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f
