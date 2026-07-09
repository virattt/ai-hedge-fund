"""Optional A-share valuation provider backed by Tushare pro ``daily_basic``.

Fills the point-in-time valuation block (market_cap / pe / pb / ps) when the
caller explicitly opts in. The default A-share layer uses free sources
(AKShare + efinance, with Yahoo Finance as a best-effort fallback) so normal
runs do not consume Tushare quota.

Token & degradation
-------------------
- Reads ``TUSHARE_TOKEN`` or ``TUSHARE_DATASETS_API_KEY`` from the environment.
  Absent → this module is a no-op (every public call returns ``None``); the
  rest of the A-share layer stays on free data sources.
- On a Tushare *permission / insufficient-points / frequency-limit* error the
  module latches a process-wide breaker so we never re-fire the gated endpoint
  per ticker.
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

# Marks non-retryable Tushare errors in exception text / error payloads.
_PERMISSION_TOKENS = (
    "权限", "permission", "积分", "40203", "40001", "40002", "40003",
    "频率", "频次", "超限", "rate limit", "frequency",
)


def _get_token() -> str:
    """Return the configured Tushare token, accepting the legacy project name."""
    return (
        os.environ.get("TUSHARE_TOKEN", "").strip()
        or os.environ.get("TUSHARE_DATASETS_API_KEY", "").strip()
    )


def _get_pro() -> Any:
    """Return a cached ``tushare.pro_api`` client, or ``None`` if no token.

    Imports ``tushare`` lazily so this module loads even when the package or
    token is absent — US-only runs and token-less CI must not break.
    """
    token = _get_token()
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
                    "tushare daily_basic unavailable for this run "
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


def get_valuation(ticker: str, as_of_date: str) -> dict | None:
    """Point-in-time valuation for ``ticker`` as of the latest trading day
    ≤ ``as_of_date``.

    ``ticker`` is a Tushare ts_code (e.g. ``600519.SH``) — the project's
    internal A-share format, no conversion needed.
    ``as_of_date`` is ``YYYY-MM-DD``.

    Returns ``{"market_cap", "pe", "pb", "ps", "trade_date"}`` or ``None``.
    ``market_cap`` is in CNY (yuan); Tushare ships it in 万元 so we multiply
    by 1e4.
    """
    if _disabled or _get_pro() is None:
        return None

    import datetime as _dt

    target = as_of_date.replace("-", "")
    dt = _dt.datetime.strptime(target, "%Y%m%d")
    # Walk back up to 7 calendar days to find a populated trading day
    # (covers the longest CN holiday closures).
    for back in range(8):
        ymd = (dt - _dt.timedelta(days=back)).strftime("%Y%m%d")
        df = _daily_basic_table(ymd)
        if df is None:
            if _disabled:
                return None
            continue  # empty/non-trading day → try the previous day
        row = df[df["ts_code"] == ticker]
        if row.empty:
            continue
        r = row.iloc[0]
        total_mv_wan = _to_float(r.get("total_mv"))
        return {
            "market_cap": total_mv_wan * 1e4 if total_mv_wan is not None else None,
            "pe": _to_float(r.get("pe")),
            "pb": _to_float(r.get("pb")),
            "ps": _to_float(r.get("ps")),
            "trade_date": ymd,
        }
    return None
