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
import math
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
    """Coerce to float, treating NaN / ±inf / None / garbage as None.

    Tushare's ``daily_basic`` computes ratios like ``pe = price / eps``, which
    is ``inf`` for loss-making tickers; letting inf through would silently
    poison downstream aggregations (mean/median PE → inf).
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):  # NaN or ±inf
        return None
    return f


def _is_permission_error(exc: BaseException | None, payload: Any) -> bool:
    """True if Tushare rejected the call for permission / points reasons.

    Tushare may raise OR return a one-row error DataFrame; handle both.
    """
    if exc is not None and any(t in str(exc) for t in _PERMISSION_TOKENS):
        return True
    if isinstance(payload, pd.DataFrame) and not payload.empty:
        cols = {str(c).lower() for c in payload.columns}
        if "code" in cols or "msg" in cols:
            joined = " ".join(str(v) for v in payload.iloc[0].tolist())
            return any(t in joined for t in _PERMISSION_TOKENS)
    return False


def _daily_basic_table(trade_date: str) -> pd.DataFrame | None:
    """Return the full-market daily_basic frame for ``trade_date`` (YYYYMMDD).

    Memoized per trade_date and serialised on a per-date lock so the fan-out
    fires one network call per date. Trips the breaker on a permission error;
    returns ``None`` (without tripping) on empty or transient errors.
    """
    global _disabled
    if _disabled:
        return None
    if trade_date in _daily_basic_tables:
        return _daily_basic_tables[trade_date]

    pro = _get_pro()
    if pro is None:
        return None

    with _cache.fetch_lock(f"tushare:daily_basic:{trade_date}"):
        if _disabled:
            return None
        if trade_date in _daily_basic_tables:
            return _daily_basic_tables[trade_date]
        try:
            df = pro.daily_basic(trade_date=trade_date)
        except Exception as e:  # noqa: BLE001 - Tushare raises varied types
            if _is_permission_error(e, None):
                logger.warning(
                    "tushare daily_basic permission denied (needs 2000 points) "
                    "— disabling Tushare valuation for this run: %s",
                    e,
                )
                _disabled = True
                return None
            # Transient: do not memoize, do not trip — let the caller retry.
            logger.warning(
                "tushare daily_basic transient error for %s: %s", trade_date, e
            )
            return None

        if _is_permission_error(None, df):
            logger.warning(
                "tushare daily_basic returned a permission-error payload "
                "— disabling Tushare valuation for this run"
            )
            _disabled = True
            return None

        if df is None or df.empty:
            return None  # non-trading day / future date — caller walks back

        _daily_basic_tables[trade_date] = df
        return df
