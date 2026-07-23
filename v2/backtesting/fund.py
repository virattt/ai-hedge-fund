"""Backtest a fund — run_cycle in a loop over history.

`run_cycle`'s docstring makes the promise: "a backtest is run_cycle in a
loop over history with a SimBroker; paper trading is the same loop on a
live clock." This module is that loop. Nothing here re-implements pipeline
mechanics — every tick is the real run_cycle against a persistent broker,
so anything true of one cycle (point-in-time data, fail-loud pricing,
master risk on the netted book) is true of every backtested tick by
construction.

Nothing here assumes what the fund trades on. The rebalance cadence comes
from the mandate (FundSpec.rebalance): a fundamentals fund says weekly, a
news-driven fund can say daily. The trading-day grid derives from the
mandate's benchmark's actual bars — holidays and half-weeks fall out
naturally, no exchange calendar math.

This is the fund-level counterpart to the per-model harness in engine.py
(BacktestEngine simulates one alpha model's views with fixed mechanics;
backtest_fund runs the whole shop).
"""

from __future__ import annotations

from datetime import date as _date
from typing import Callable

import numpy as np
from pydantic import BaseModel

from v2.brokers.sim import SimBroker
from v2.data.protocol import DataClient
from v2.fund.spec import Fund
from v2.pipeline.models import CycleRecord
from v2.pipeline.run_cycle import run_cycle

_PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}


class FundBacktestMetrics(BaseModel):
    """The numbers that say whether the fund worked, and against what."""

    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    benchmark_return_pct: float
    excess_return_pct: float          # fund total minus benchmark total
    n_cycles: int
    n_orders: int


class FundBacktestResult(BaseModel):
    """A full backtest, serialized: the curve, the stats, and — because every
    tick is a CycleRecord — every thesis, clamp, order, and fill behind it.
    `model_dump_json()` round-trips; this is the receipts file."""

    fund: str
    start: str                        # first grid date actually traded
    end: str                          # last grid date actually traded
    rebalance: str
    benchmark: str
    capital: float
    dates: list[str]
    nav: list[float]                  # NAV after each cycle, one per date
    benchmark_nav: list[float]        # benchmark scaled to the same capital
    metrics: FundBacktestMetrics
    records: list[CycleRecord]


def backtest_fund(
    fund: Fund,
    start: str,
    end: str,
    data_client: DataClient,
    *,
    on_cycle: Callable[[int, int, CycleRecord], None] | None = None,
) -> FundBacktestResult:
    """Run *fund* through history from *start* to *end* (YYYY-MM-DD).

    One run_cycle per grid date against a persistent SimBroker — positions
    and cash carry across ticks, so the fund rebalances rather than
    restarts. `on_cycle(i, n, record)` fires after each tick (progress UIs).

    Fail loud: no benchmark bars in the window raises — a backtest with no
    trading grid is an infrastructure problem, not an empty result.
    """
    spec = fund.spec
    bars = data_client.get_prices(spec.benchmark, start, end)
    closes = {b.time[:10]: b.close for b in bars if start <= b.time[:10] <= end}
    if not closes:
        raise ValueError(
            f"{spec.name}: no {spec.benchmark} bars in [{start}, {end}] — "
            "cannot build the trading grid"
        )
    grid = rebalance_grid(sorted(closes), spec.rebalance)

    broker = SimBroker(cash=spec.capital)
    records: list[CycleRecord] = []
    nav: list[float] = []
    benchmark_nav: list[float] = []
    base_close = closes[grid[0]]
    for i, as_of in enumerate(grid):
        record = run_cycle(fund, as_of, broker, data_client)
        records.append(record)
        nav.append(record.nav)
        benchmark_nav.append(spec.capital * closes[as_of] / base_close)
        if on_cycle is not None:
            on_cycle(i, len(grid), record)

    return FundBacktestResult(
        fund=spec.name,
        start=grid[0],
        end=grid[-1],
        rebalance=spec.rebalance,
        benchmark=spec.benchmark,
        capital=spec.capital,
        dates=grid,
        nav=nav,
        benchmark_nav=benchmark_nav,
        metrics=_metrics(spec.capital, grid, nav, benchmark_nav,
                         spec.rebalance, records),
        records=records,
    )


def rebalance_grid(days: list[str], cadence: str) -> list[str]:
    """Pick the rebalance dates out of sorted trading *days* (YYYY-MM-DD).

    daily: every day. weekly: the last trading day of each ISO week.
    monthly: the last trading day of each calendar month.
    """
    if cadence == "daily":
        return list(days)
    if cadence not in ("weekly", "monthly"):
        raise ValueError(f"unknown rebalance cadence {cadence!r}")

    last_of_period: dict[tuple[int, int], str] = {}
    for day in days:
        d = _date.fromisoformat(day)
        if cadence == "weekly":
            iso = d.isocalendar()
            key = (iso[0], iso[1])
        else:
            key = (d.year, d.month)
        last_of_period[key] = day  # days are sorted — the last write wins
    return sorted(last_of_period.values())


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _metrics(
    capital: float,
    grid: list[str],
    nav: list[float],
    benchmark_nav: list[float],
    cadence: str,
    records: list[CycleRecord],
) -> FundBacktestMetrics:
    total = nav[-1] / capital - 1

    calendar_days = (_date.fromisoformat(grid[-1]) - _date.fromisoformat(grid[0])).days
    years = max(calendar_days / 365.25, 0.01)
    annualized = (1 + total) ** (1 / years) - 1

    # Per-period returns over the curve including the starting capital, so
    # the first tick's move counts too.
    curve = np.array([capital] + nav)
    returns = curve[1:] / curve[:-1] - 1
    if len(returns) > 1 and float(returns.std(ddof=1)) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=1)) * np.sqrt(
            _PERIODS_PER_YEAR[cadence]
        )
    else:
        sharpe = 0.0

    peak = curve[0]
    max_dd = 0.0
    for value in curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_dd:
            max_dd = drawdown

    benchmark_return = benchmark_nav[-1] / capital - 1

    return FundBacktestMetrics(
        total_return_pct=round(total, 6),
        annualized_return_pct=round(annualized, 6),
        sharpe_ratio=round(float(sharpe), 4),
        max_drawdown_pct=round(float(max_dd), 6),
        benchmark_return_pct=round(benchmark_return, 6),
        excess_return_pct=round(total - benchmark_return, 6),
        n_cycles=len(nav),
        n_orders=sum(len(r.orders) for r in records),
    )
