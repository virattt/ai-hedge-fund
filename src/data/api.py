"""Data abstraction layer for price and token metrics."""

from __future__ import annotations

import datetime as _dt
from typing import Any

from src.config import IS_CRYPTO
from src.data.cache import get_cache

if IS_CRYPTO:
    import ccxt  # type: ignore
    from pycoingecko import CoinGeckoAPI  # type: ignore

from src.tools.api import get_prices

_cache = get_cache()


def _parse_timestamp(ts: int) -> str:
    return _dt.datetime.utcfromtimestamp(ts / 1000).isoformat()


def get_crypto_ohlcv_ccxt(pair: str, start: str, end: str, timeframe: str = "1d", exchange: str = "binance") -> list[dict[str, Any]]:
    """Fetch OHLCV for a crypto pair via CCXT.

    Args:
        pair: Trading pair like ``"BTC/USDT"``.
        start: ISO8601 start time.
        end: ISO8601 end time.
        timeframe: Bar size (e.g. ``"1h"``).
        exchange: Exchange id compatible with CCXT.

    Returns:
        List of OHLCV dictionaries.
    """
    ex = getattr(ccxt, exchange)()  # type: ignore[attr-defined]
    since = ex.parse8601(start)
    end_ms = ex.parse8601(end)
    all_bars: list[list[Any]] = []
    limit = 1000
    while since < end_ms:
        data = ex.fetch_ohlcv(pair, timeframe=timeframe, since=since, limit=limit)
        if not data:
            break
        all_bars.extend(data)
        since = data[-1][0] + ex.parse_timeframe(timeframe) * 1000
        if len(data) < limit:
            break
    bars = [b for b in all_bars if b[0] <= end_ms]
    return [
        {
            "open": b[1],
            "high": b[2],
            "low": b[3],
            "close": b[4],
            "volume": b[5],
            "time": _parse_timestamp(b[0]),
        }
        for b in bars
    ]


def get_token_metrics(id_or_symbol: str) -> dict[str, Any]:
    """Fetch token metrics from CoinGecko."""
    cg = CoinGeckoAPI()
    try:
        data = cg.get_coin_by_id(id_or_symbol)
    except Exception:
        data = cg.get_coin_by_id(id_or_symbol.lower())
    return data


def get_price_ohlcv(symbol_or_pair: str, start: str, end: str, timeframe: str = "1d", exchange: str = "binance") -> list[dict[str, Any]]:
    """Unified price fetcher. Routes to Yahoo or CCXT based on ``config.IS_CRYPTO``."""
    if IS_CRYPTO:
        cache_key = f"{symbol_or_pair}_{exchange}_{timeframe}_{start}_{end}"
        if cached := _cache.get_prices(cache_key):
            return cached
        bars = get_crypto_ohlcv_ccxt(symbol_or_pair, start, end, timeframe, exchange)
        _cache.set_prices(cache_key, bars)
        return bars
    else:
        prices = get_prices(symbol_or_pair, start, end)
        return [p.model_dump() for p in prices]
