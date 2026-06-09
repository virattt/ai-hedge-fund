"""Quarterly revenue + QoQ growth-rate analysis (powers revenue_acceleration source)."""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field

import yfinance as yf

from ._helpers import CACHE_MAX_SIZE, CACHE_TTL_SECONDS, stringify_period

logger = logging.getLogger(__name__)

_MIN_QUARTERS = 4


@dataclass
class RevenuePoint:
    period_end: str
    revenue: float


@dataclass
class RevenueGrowthAnalysis:
    ticker: str
    quarters: list[RevenuePoint] = field(default_factory=list)
    qoq_growth_pcts: list[float] = field(default_factory=list)
    consecutive_accelerating: int = 0
    latest_qoq_growth_pct: float | None = None
    is_shrinking: bool = False
    has_data: bool = False


_cache: OrderedDict[str, tuple[RevenueGrowthAnalysis | None, float]] = OrderedDict()


def _cache_get(key: str) -> RevenueGrowthAnalysis | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.monotonic() - ts > CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: RevenueGrowthAnalysis | None) -> None:
    _cache[key] = (value, time.monotonic())
    while len(_cache) > CACHE_MAX_SIZE:
        _cache.popitem(last=False)


def _extract_quarterly_revenue_sync(ticker: str) -> list[RevenuePoint]:
    """Pull 8 quarters of revenue from yfinance, oldest-first."""
    try:
        t = yf.Ticker(ticker.upper())
        income = t.quarterly_income_stmt
        if income is None or income.empty:
            income = t.quarterly_financials
    except Exception as exc:
        logger.debug("fundamentals: yfinance income fetch failed for %s: %s", ticker, exc)
        return []

    if income is None or income.empty:
        return []

    revenue_row = None
    for candidate in ("Total Revenue", "Revenue", "TotalRevenue", "Operating Revenue"):
        if candidate in income.index:
            revenue_row = income.loc[candidate]
            break
    if revenue_row is None:
        return []

    points: list[RevenuePoint] = []
    for period, value in revenue_row.items():
        if value is None:
            continue
        try:
            revenue_val = float(value)
        except (TypeError, ValueError):
            continue
        if revenue_val <= 0:
            continue
        try:
            period_str = stringify_period(period)
        except Exception:
            continue
        if not period_str:
            continue
        points.append(RevenuePoint(period_end=period_str, revenue=revenue_val))

    points.sort(key=lambda p: p.period_end)
    return points[-8:]


def _compute_analysis(ticker: str, points: list[RevenuePoint]) -> RevenueGrowthAnalysis:
    if len(points) < _MIN_QUARTERS:
        return RevenueGrowthAnalysis(ticker=ticker.upper(), quarters=points)

    growth_pcts: list[float] = []
    for i in range(1, len(points)):
        prev = points[i - 1].revenue
        cur = points[i].revenue
        if prev <= 0:
            continue
        growth_pcts.append((cur / prev - 1.0) * 100.0)

    if not growth_pcts:
        return RevenueGrowthAnalysis(ticker=ticker.upper(), quarters=points)

    latest = growth_pcts[-1]
    is_shrinking = latest < 0

    consecutive = 0
    for i in range(len(growth_pcts) - 1, 0, -1):
        if growth_pcts[i] > growth_pcts[i - 1]:
            consecutive += 1
        else:
            break

    return RevenueGrowthAnalysis(
        ticker=ticker.upper(),
        quarters=points,
        qoq_growth_pcts=growth_pcts,
        consecutive_accelerating=consecutive,
        latest_qoq_growth_pct=latest,
        is_shrinking=is_shrinking,
        has_data=True,
    )


async def get_revenue_growth(ticker: str) -> RevenueGrowthAnalysis | None:
    """Cached: pull revenue history and compute acceleration analysis."""
    cache_key = ticker.upper()
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    points = await asyncio.to_thread(_extract_quarterly_revenue_sync, ticker)
    result = _compute_analysis(ticker, points)
    _cache_put(cache_key, result)
    return result


async def get_revenue_growth_batch(tickers: list[str]) -> dict[str, RevenueGrowthAnalysis | None]:
    """Concurrent fetch for many tickers."""
    if not tickers:
        return {}
    tasks = [get_revenue_growth(t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, RevenueGrowthAnalysis | None] = {}
    for t, res in zip(tickers, results, strict=True):
        if isinstance(res, BaseException):
            logger.debug("fundamentals: batch fetch error for %s: %s", t, res)
            out[t.upper()] = None
        else:
            out[t.upper()] = res
    return out
