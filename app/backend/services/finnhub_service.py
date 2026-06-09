"""Short interest service using yfinance.

Fetches short interest metrics from Yahoo Finance via the yfinance library.
All responses are cached for 1 hour in an OrderedDict-based LRU+TTL cache,
following the openinsider_service pattern.

No API key required — yfinance is free and open.
"""

import asyncio
import logging
import time
from collections import OrderedDict

import yfinance as yf

from app.backend.models.finnhub_schemas import ShortInterestData, ShortInterestResponse, SqueezeCandidate, SqueezeScreenerResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS: float = 3600.0  # 1 hour
_CACHE_MAX_SIZE: int = 50

# ---------------------------------------------------------------------------
# LRU+TTL cache
# ---------------------------------------------------------------------------

_cache: OrderedDict[str, tuple[object, float]] = OrderedDict()


def _cache_get(cache_key: str) -> object | None:
    entry = _cache.get(cache_key)
    if entry is None:
        return None
    response, timestamp = entry
    if time.monotonic() - timestamp > _CACHE_TTL_SECONDS:
        _cache.pop(cache_key, None)
        return None
    return response


def _cache_put(cache_key: str, response: object) -> None:
    _cache[cache_key] = (response, time.monotonic())
    while len(_cache) > _CACHE_MAX_SIZE:
        _cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ShortInterestFetchError(Exception):
    """Raised when short interest data cannot be fetched."""


# ---------------------------------------------------------------------------
# Synchronous fetch workers
# ---------------------------------------------------------------------------


def _fetch_short_interest(symbol: str) -> ShortInterestResponse:
    """Fetch short interest metrics for a single symbol using yfinance."""
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info
    except Exception as exc:
        raise ShortInterestFetchError(f"Failed to fetch yfinance data for {symbol}: {exc}") from exc

    if not info or info.get("trailingPegRatio") is None and info.get("shortPercentOfFloat") is None and len(info) <= 1:
        return ShortInterestResponse(symbol=symbol.upper(), data=None, cached=False)

    short_pct = info.get("shortPercentOfFloat")
    short_ratio = info.get("shortRatio")
    shares_short = info.get("sharesShort")
    float_shares = info.get("floatShares")

    # Convert shortPercentOfFloat from decimal (0.0123) to percentage (1.23)
    if short_pct is not None:
        short_pct = round(short_pct * 100, 2)

    short_data = ShortInterestData(
        symbol=symbol.upper(),
        short_pct_float=short_pct,
        days_to_cover=short_ratio,
        shares_short=shares_short,
        float_shares=float_shares,
    )

    return ShortInterestResponse(symbol=symbol.upper(), data=short_data, cached=False)


# ---------------------------------------------------------------------------
# Async entry points
# ---------------------------------------------------------------------------


async def get_short_interest(symbol: str) -> ShortInterestResponse:
    """Async entry point for short interest data for a single symbol."""
    cache_key = f"yf:short_interest:{symbol.upper()}"

    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, ShortInterestResponse):
        return ShortInterestResponse(
            symbol=cached.symbol,
            data=cached.data,
            cached=True,
        )

    result = await asyncio.to_thread(_fetch_short_interest, symbol)
    _cache_put(cache_key, result)
    return result


async def get_squeeze_candidates() -> SqueezeScreenerResponse:
    """Cross-reference OpenInsider cluster buys with yfinance short interest.

    Fetches recent cluster buys from OpenInsider, then for each unique ticker
    fetches short interest from yfinance to find squeeze candidates.
    """
    cache_key = "yf:squeeze_screener"

    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, SqueezeScreenerResponse):
        return cached

    # Get OpenInsider cluster buys first — these are stocks insiders are buying
    from app.backend.services.openinsider_service import get_openinsider_screener, OpenInsiderFetchError

    insider_buys_by_ticker: dict[str, list] = {}
    try:
        oi_response = await get_openinsider_screener("latest_cluster_buys", None)
        for record in oi_response.records:
            ticker = record.ticker.upper()
            if ticker not in insider_buys_by_ticker:
                insider_buys_by_ticker[ticker] = []
            insider_buys_by_ticker[ticker].append(record)
    except OpenInsiderFetchError:
        logger.warning("Could not fetch OpenInsider data for squeeze screener")

    # For each unique ticker with insider buys, fetch short interest from yfinance
    candidates: list[SqueezeCandidate] = []
    for ticker, buys in insider_buys_by_ticker.items():
        try:
            si_response = await asyncio.to_thread(_fetch_short_interest, ticker)
            si = si_response.data
        except ShortInterestFetchError:
            logger.debug("Could not fetch yfinance data for %s", ticker)
            si = None

        company_name = buys[0].company_name if buys else ""
        candidates.append(SqueezeCandidate(
            ticker=ticker,
            company_name=company_name,
            short_pct_float=si.short_pct_float if si else None,
            days_to_cover=si.days_to_cover if si else None,
            shares_short=si.shares_short if si else None,
            insider_buy_count=len(buys),
            insider_buy_value=sum(b.value or 0 for b in buys),
            latest_insider_buy_date=buys[0].trade_date if buys else None,
        ))

    # Sort: highest short float first (best squeeze potential)
    candidates.sort(key=lambda c: (c.short_pct_float or 0), reverse=True)

    result = SqueezeScreenerResponse(candidates=candidates, total=len(candidates))
    _cache_put(cache_key, result)
    return result
