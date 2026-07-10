"""Yahoo Finance fallback data source for A-share tickers.

This module is intentionally small and best-effort. Yahoo Finance coverage for
Chinese A-shares is useful for daily prices and current quote fields, but it is
not a point-in-time fundamentals source like Tushare ``daily_basic``.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import pandas as pd

from src.data.models import Price
from src.tools.markets import a_share_code

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised through monkeypatched module in tests
    import yfinance as yf
except Exception:  # noqa: BLE001 - optional dependency fallback
    yf = None


def yahoo_ticker(ticker: str) -> str | None:
    """Convert a Tushare-style A-share ticker to Yahoo Finance format."""
    code = a_share_code(ticker)
    if ticker.endswith(".SH"):
        return f"{code}.SS"
    if ticker.endswith(".SZ"):
        return f"{code}.SZ"
    if ticker.endswith(".BJ"):
        return None
    return ticker


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return result


def _to_end_exclusive(end_date: str) -> str:
    """Yahoo's historical download end date is exclusive."""
    parsed = dt.datetime.strptime(end_date, "%Y-%m-%d").date()
    return (parsed + dt.timedelta(days=1)).isoformat()


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch daily OHLCV from Yahoo Finance as a fallback."""
    if yf is None:
        return []

    symbol = yahoo_ticker(ticker)
    if not symbol:
        return []

    try:
        df = yf.download(
            symbol,
            start=start_date,
            end=_to_end_exclusive(end_date),
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
        )
    except Exception as e:  # noqa: BLE001 - yfinance raises varied exceptions
        logger.warning("yfinance get_prices failed for %s: %s", ticker, e)
        return []

    if df is None or df.empty:
        return []

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    prices: list[Price] = []
    for index, row in df.iterrows():
        try:
            open_ = _to_float(row.get("Open"))
            close = _to_float(row.get("Close"))
            high = _to_float(row.get("High"))
            low = _to_float(row.get("Low"))
            volume = _to_float(row.get("Volume"))
            if None in (open_, close, high, low, volume):
                continue
            prices.append(
                Price(
                    time=str(pd.Timestamp(index).date()),
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


def get_market_cap(ticker: str) -> float | None:
    """Fetch current market cap from Yahoo Finance quote fields."""
    if yf is None:
        return None

    symbol = yahoo_ticker(ticker)
    if not symbol:
        return None

    try:
        quote = yf.Ticker(symbol)
        fast_info = getattr(quote, "fast_info", None)
        if fast_info:
            cap = _to_float(fast_info.get("marketCap"))
            if cap and cap > 0:
                return cap
        info = getattr(quote, "info", None) or {}
        cap = _to_float(info.get("marketCap"))
        if cap and cap > 0:
            return cap
    except Exception as e:  # noqa: BLE001 - yfinance raises varied exceptions
        logger.warning("yfinance get_market_cap failed for %s: %s", ticker, e)
    return None
