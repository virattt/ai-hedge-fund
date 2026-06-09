"""ROIC history — multi-year return on invested capital from yfinance statements.

ROIC ≈ EBIT × (1 - effective_tax_rate) / (Total Debt + Total Equity).
Falls back to operatingIncome when EBIT is missing, assumes 21% tax when the
tax line is unavailable. Three-year monotonic-increase flag drives the
high_roic Discovery source's top tier.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Protocol, cast

import yfinance as yf

from ._helpers import (
    CACHE_MAX_SIZE,
    CACHE_TTL_SECONDS,
    line_item,
    safe_float,
    stringify_period,
)

logger = logging.getLogger(__name__)


class _SeriesProto(Protocol):
    """Minimal pandas Series surface — index for iteration, __getitem__ for lookup."""
    index: object


@dataclass
class RoicYear:
    period_end: str
    roic_pct: float


@dataclass
class RoicHistory:
    ticker: str
    years: list[RoicYear] = field(default_factory=list)
    latest_roic_pct: float | None = None
    is_increasing_3y: bool = False
    has_data: bool = False


_cache: OrderedDict[str, tuple[RoicHistory | None, float]] = OrderedDict()


def _cache_get(key: str) -> RoicHistory | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.monotonic() - ts > CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: RoicHistory | None) -> None:
    _cache[key] = (value, time.monotonic())
    while len(_cache) > CACHE_MAX_SIZE:
        _cache.popitem(last=False)


def _safe_period_value(row: object, period: object) -> float | None:
    """Pull a numeric value from a Series-like row by column key."""
    if row is None:
        return None
    try:
        value = row[period]  # pyright: ignore[reportIndexIssue] - pandas Series, dynamic at runtime; try/except below catches the access failure modes
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    return safe_float(value)


def _row_periods(row: object) -> list[object]:
    """Return the list of period labels (column keys) for a Series-like row."""
    if row is None:
        return []
    try:
        index = cast(_SeriesProto, row).index
    except AttributeError:
        return []
    try:
        return list(index)
    except TypeError:
        return []


def _fetch_roic_history_sync(ticker: str) -> RoicHistory | None:
    """Compute approximate ROIC per fiscal year from yfinance statements."""
    try:
        t = yf.Ticker(ticker.upper())
        income = t.income_stmt
        balance = t.balance_sheet
    except Exception as exc:
        logger.debug("fundamentals: yfinance income/balance fetch failed for %s: %s", ticker, exc)
        return None

    if income is None or balance is None:
        return None
    try:
        if income.empty or balance.empty:
            return None
    except AttributeError:
        return None

    ebit_row = line_item(income, ("EBIT", "Operating Income", "OperatingIncome"))
    pretax_row = line_item(income, ("Pretax Income", "Income Before Tax"))
    tax_row = line_item(income, ("Tax Provision", "Income Tax Expense"))
    debt_row = line_item(balance, ("Total Debt", "Long Term Debt"))
    equity_row = line_item(balance, ("Stockholders Equity", "Total Equity Gross Minority Interest"))

    if ebit_row is None or equity_row is None:
        return None

    ebit_periods = _row_periods(ebit_row)
    if not ebit_periods:
        return None

    years: list[RoicYear] = []
    for period in ebit_periods:
        ebit = _safe_period_value(ebit_row, period)
        if ebit is None:
            continue
        equity = _safe_period_value(equity_row, period) or 0.0
        debt = _safe_period_value(debt_row, period) or 0.0
        invested_capital = debt + equity
        if invested_capital <= 0:
            continue

        tax_rate = 0.21
        pretax = _safe_period_value(pretax_row, period)
        tax = _safe_period_value(tax_row, period)
        if pretax is not None and tax is not None and pretax > 0 and tax >= 0:
            tax_rate = max(0.0, min(0.5, tax / pretax))

        nopat = ebit * (1 - tax_rate)
        roic_pct = (nopat / invested_capital) * 100.0
        try:
            period_str = stringify_period(period)
        except Exception:
            continue
        years.append(RoicYear(period_end=period_str, roic_pct=roic_pct))

    if not years:
        return None

    years.sort(key=lambda y: y.period_end)
    recent = years[-3:]
    is_increasing = (
        len(recent) >= 3
        and recent[2].roic_pct > recent[1].roic_pct
        and recent[1].roic_pct > recent[0].roic_pct
    )

    return RoicHistory(
        ticker=ticker.upper(),
        years=years,
        latest_roic_pct=years[-1].roic_pct,
        is_increasing_3y=is_increasing,
        has_data=True,
    )


async def get_roic_history(ticker: str) -> RoicHistory | None:
    cache_key = ticker.upper()
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    result = await asyncio.to_thread(_fetch_roic_history_sync, ticker)
    _cache_put(cache_key, result)
    return result


async def get_roic_history_batch(tickers: list[str]) -> dict[str, RoicHistory | None]:
    if not tickers:
        return {}
    tasks = [get_roic_history(t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, RoicHistory | None] = {}
    for t, res in zip(tickers, results, strict=True):
        if isinstance(res, BaseException):
            logger.debug("fundamentals: batch ROIC error for %s: %s", t, res)
            out[t.upper()] = None
        else:
            out[t.upper()] = res
    return out
