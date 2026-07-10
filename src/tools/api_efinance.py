"""EFinance fallback data source for A-share tickers.

EFinance is a free Eastmoney-backed data source. It is used after the existing
AKShare paths and before non-mainland fallbacks for A-share prices and current
valuation snapshots.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.data.cache import get_cache
from src.data.models import Price
from src.tools.markets import a_share_code

logger = logging.getLogger(__name__)

_cache = get_cache()
ef = None
_realtime_quotes: pd.DataFrame | None = None
_realtime_quotes_attempted = False


def _get_efinance():
    """Import efinance lazily because it may create local cache files on import."""
    global ef
    if ef is not None:
        return ef
    try:
        import efinance as imported_ef
    except Exception as e:  # noqa: BLE001 - optional dependency / cache-dir issues
        logger.warning("efinance import failed: %s", e)
        return None
    ef = imported_ef
    return ef


def _safe_float(value: Any) -> float | None:
    if value is None or value == "-":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return result


def _first_present(row: pd.Series, names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch A-share daily OHLCV from efinance."""
    client = _get_efinance()
    if client is None:
        return []

    code = a_share_code(ticker)
    try:
        df = client.stock.get_quote_history(
            code,
            beg=start_date.replace("-", ""),
            end=end_date.replace("-", ""),
            klt=101,
            fqt=1,
            suppress_error=True,
            use_id_cache=True,
        )
    except Exception as e:  # noqa: BLE001 - efinance raises varied exceptions
        logger.warning("efinance get_prices failed for %s: %s", ticker, e)
        return []

    if df is None or df.empty:
        return []

    prices: list[Price] = []
    for _, row in df.iterrows():
        try:
            open_ = _safe_float(_first_present(row, ("开盘", "open", "Open")))
            close = _safe_float(_first_present(row, ("收盘", "close", "Close")))
            high = _safe_float(_first_present(row, ("最高", "high", "High")))
            low = _safe_float(_first_present(row, ("最低", "low", "Low")))
            volume = _safe_float(_first_present(row, ("成交量", "volume", "Volume")))
            time = _first_present(row, ("日期", "time", "date", "Date"))
            if None in (open_, close, high, low, volume) or time is None:
                continue
            prices.append(
                Price(
                    time=str(time),
                    open=open_,
                    close=close,
                    high=high,
                    low=low,
                    volume=int(volume),
                )
            )
        except (TypeError, ValueError):
            continue
    return prices


def _get_realtime_quotes() -> pd.DataFrame | None:
    """Fetch and memoize the all-A-share realtime quote table."""
    global _realtime_quotes, _realtime_quotes_attempted
    if _realtime_quotes is not None:
        return _realtime_quotes
    if _realtime_quotes_attempted:
        return None

    client = _get_efinance()
    if client is None:
        _realtime_quotes_attempted = True
        return None

    with _cache.fetch_lock("efinance:realtime_quotes"):
        if _realtime_quotes is not None:
            return _realtime_quotes
        if _realtime_quotes_attempted:
            return None
        _realtime_quotes_attempted = True
        try:
            df = client.stock.get_realtime_quotes()
        except Exception as e:  # noqa: BLE001 - efinance raises varied exceptions
            logger.warning("efinance get_realtime_quotes failed: %s", e)
            return None
        if df is None or df.empty:
            return None
        _realtime_quotes = df
        return _realtime_quotes


def get_realtime_valuation(ticker: str) -> dict[str, float | None] | None:
    """Return current market cap and ratios from efinance realtime quotes."""
    df = _get_realtime_quotes()
    if df is None or df.empty or "股票代码" not in df.columns:
        return None

    code = a_share_code(ticker)
    row = df[df["股票代码"].astype(str).str.zfill(6) == code]
    if row.empty:
        return None

    item = row.iloc[0]
    result = {
        "market_cap": _safe_float(item.get("总市值")),
        "pe": _safe_float(item.get("动态市盈率")),
        "pb": _safe_float(item.get("市净率")),
        "ps": _safe_float(item.get("市销率")),
    }
    if not any(v is not None and v > 0 for v in result.values()):
        return None
    return result


def get_market_cap(ticker: str) -> float | None:
    valuation = get_realtime_valuation(ticker)
    if valuation and valuation.get("market_cap"):
        return valuation["market_cap"]
    return None
