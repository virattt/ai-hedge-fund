"""Earnings Sentiment service — FMP transcripts + EDGAR fallback + LLM analysis.

Fetches earnings call transcripts from the FMP API (primary) or SEC EDGAR 8-K
filings (fallback), runs LLM-powered sentiment analysis, computes sentiment
delta between consecutive quarters, and cross-references with OpenInsider data
for conviction scoring.

Cache: 6-hour TTL, 30-max entries (transcripts change infrequently).
"""

import asyncio
import time
from collections import OrderedDict

from app.backend.models.earnings_schemas import (
    ConvictionResponse,
    EarningsAnalysisResponse,
)

from ._analysis import EarningsLLMError, build_conviction_signals, build_earnings_analysis
from ._fetch import EarningsFetchError

_CACHE_TTL_SECONDS: float = 21600.0  # 6 hours
_CACHE_MAX_SIZE: int = 30

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


async def get_earnings_analysis(ticker: str, model_name: str, model_provider: str, api_keys: dict) -> EarningsAnalysisResponse:
    cache_key = f"earnings:analysis:{ticker.upper()}:{model_name}"
    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, EarningsAnalysisResponse):
        return EarningsAnalysisResponse(ticker=cached.ticker, transcripts=cached.transcripts, delta=cached.delta, cached=True)

    result = await asyncio.to_thread(build_earnings_analysis, ticker, model_name, model_provider, api_keys)
    _cache_put(cache_key, result)
    return result


async def get_conviction_signals(tickers: list[str], model_name: str, model_provider: str, api_keys: dict) -> ConvictionResponse:
    cache_key = f"earnings:conviction:{','.join(sorted(t.upper() for t in tickers))}:{model_name}"
    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, ConvictionResponse):
        return ConvictionResponse(signals=cached.signals, total=cached.total, cached=True)

    result = await asyncio.to_thread(build_conviction_signals, tickers, model_name, model_provider, api_keys)
    _cache_put(cache_key, result)
    return result
