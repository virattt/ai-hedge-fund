"""Backtest a fund — `advance` in a loop over history.

`advance` is the fund's daily unit of work (hedge_fund/pipeline/session.py).
This module is the historical clock around it: every benchmark session in
the window, in order, against an in-memory FundState and a fresh SimBroker.
Nothing here re-implements pipeline mechanics, so anything true of one
session (point-in-time data, next-close execution, reconciliation, master
risk on the netted book) is true of every backtested session by
construction — and identical to what a paper fund does, one tick at a time.

The trading grid derives from the mandate's benchmark's actual bars —
holidays and half-weeks fall out naturally, no exchange calendar math. A
minute fund's grid is its own: every bar of its window on each of those
days, marked from 1-minute history (`BarClock`); an interval under a minute
is backtested at one minute, the finest history there is, and the result
says so.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Callable, Literal

import numpy as np
from pydantic import BaseModel

from hedge_fund.brokers.sim import SimBroker
from hedge_fund.data.bars import bar_grid, bars_per_day
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import previous_day, session_closes
from hedge_fund.fund import format_interval, Fund, FundSpec, normalize_universe
from hedge_fund.pipeline.clock import BarClock, Clock, DailyClock
from hedge_fund.pipeline.models import CycleRecord
from hedge_fund.pipeline.session import (
    advance,
    FundState,
    is_rebalance_session,
    next_state,
    SessionRecord,
)

BACKTEST_FLOOR_SECONDS = 60  # the finest bar history has: sub-minute mandates replay at 1m


class ReplaySchedule(BaseModel):
    """Observed sessions and the assessment dates required for replay and warming."""

    closes: dict[str, float]
    execution_dates: dict[str, str | None]

    @property
    def assessment_dates(self) -> list[str]:
        return sorted(set(self.execution_dates) | {
            previous_day(session) for session in self.execution_dates.values()
            if session is not None
        })


def build_schedule(data: DataClient, benchmark: str, start: str, end: str, cadence: str) -> ReplaySchedule:
    closes = session_closes(data, benchmark, start, end)
    if not closes:
        raise ValueError(f"no {benchmark} bars in [{start}, {end}] — cannot build the trading grid")
    days = list(closes)
    following = dict(zip(days, days[1:]))
    return ReplaySchedule(closes=closes, execution_dates={
        day: following.get(day) for day in rebalance_grid(days, cadence)
    })


class DailyValuation(BaseModel):
    as_of: str
    nav: float
    benchmark_nav: float


class FundBacktestMetrics(BaseModel):
    """The numbers that say whether the fund worked, and against what."""

    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    benchmark_return_pct: float
    excess_return_pct: float          # fund total minus benchmark total
    n_cycles: int                     # executed rebalances
    n_orders: int


class FundBacktestResult(BaseModel):
    """A full backtest, serialized: the curve, the stats, and — because every
    session is a SessionRecord — every thesis, clamp, order, and fill behind
    it. `model_dump_json()` round-trips; this is the research artifact."""

    schema_version: Literal[2] = 2
    fund: str
    start: str                        # first valuation session
    end: str                          # last valuation session
    rebalance: str
    benchmark: str
    universe: list[str]               # the tickers this backtest was run over
    capital: float
    dates: list[str]
    nav: list[float]                  # closing NAV for every observed session
    benchmark_nav: list[float]        # benchmark scaled to the same capital
    metrics: FundBacktestMetrics
    records: list[SessionRecord]      # one per session, in order

    @property
    def cycles(self) -> list[CycleRecord]:
        """The executed rebalances, in order."""
        return [r.executed for r in self.records if r.executed is not None]


def backtest_fund(
    fund: Fund, start: str, end: str, data_client: DataClient, universe: list[str], *,
    on_cycle: Callable[[int, int, CycleRecord], None] | None = None,
    on_valuation: Callable[[int, int, DailyValuation], None] | None = None,
) -> FundBacktestResult:
    """Replay *fund* over *universe* through every benchmark session in [start, end].

    `on_cycle(i, n, cycle)` fires after each executed rebalance and
    `on_valuation(i, n, value)` after every session's close; both receive a
    zero-based index and the total count. A decision made at the window's
    last session stays on that record, unexecuted.

    Fail loud: no benchmark bars in the window raises — a backtest with no
    trading grid is an infrastructure problem, not an empty result.
    """
    spec = fund.spec
    universe = normalize_universe(universe)
    closes = session_closes(data_client, spec.benchmark, start, end)
    if not closes:
        raise ValueError(
            f"{spec.name}: no {spec.benchmark} bars in [{start}, {end}] — "
            "cannot build the trading grid"
        )
    days = list(closes)
    dates, clock, cadence, periods_per_year = replay_grid(spec, days, data_client)
    n_cycles = sum(1 for day in rebalance_grid(dates, spec.rebalance) if day != dates[-1])

    broker = SimBroker(cash=spec.capital)
    state = FundState.initial(spec.capital)
    records: list[SessionRecord] = []
    nav: list[float] = []
    benchmark_nav: list[float] = []
    base_close: float | None = None
    n_executed = 0
    for i, session in enumerate(dates):
        record = advance(fund, state, session, broker, data_client, universe, clock)
        state = next_state(state, record)
        records.append(record)
        nav.append(record.nav)
        base_close = base_close or record.benchmark_close
        benchmark_nav.append(spec.capital * record.benchmark_close / base_close)
        if record.executed is not None:
            if on_cycle is not None:
                on_cycle(n_executed, n_cycles, record.executed)
            n_executed += 1
        if on_valuation is not None:
            on_valuation(i, len(dates), DailyValuation(
                as_of=session, nav=nav[-1], benchmark_nav=benchmark_nav[-1],
            ))

    cycles = [r.executed for r in records if r.executed is not None]
    return FundBacktestResult(
        fund=spec.name, start=dates[0], end=dates[-1], rebalance=cadence,
        benchmark=spec.benchmark, universe=universe, capital=spec.capital,
        dates=dates, nav=nav, benchmark_nav=benchmark_nav,
        metrics=performance_metrics(spec.capital, dates, nav, benchmark_nav, cycles,
                                    periods_per_year=periods_per_year),
        records=records,
    )


def replay_grid(spec: FundSpec, days: list[str], data: DataClient) -> tuple[list[str], Clock, str, float]:
    """The sessions a backtest steps through, the clock that marks them, the
    cadence as the result will name it, and the sessions in a year (for
    annualizing). Daily mandates: the benchmark's *days* themselves. Minute
    mandates: every bar of the window on each of those days, at the
    mandate's interval or one minute, whichever is coarser."""
    if not spec.is_intraday:
        return days, DailyClock(data), spec.rebalance, 252
    seconds = max(BACKTEST_FLOOR_SECONDS, round(spec.interval_seconds / 60) * 60)
    sessions = [bar for day in days for bar in bar_grid(day, seconds, spec.window)]
    cadence = f"every {format_interval(seconds)} · {spec.window.label}"
    if seconds != spec.interval_seconds:
        cadence += f" (mandate: {spec.cadence_label}; backtested at the 1-minute bars history has)"
    return sessions, BarClock(data, seconds, spec.window), cadence, bars_per_day(seconds, spec.window) * 252


def rebalance_grid(days: list[str], cadence: str) -> list[str]:
    """Pick the rebalance dates out of sorted trading *days* (YYYY-MM-DD).

    daily: every day. weekly: the first trading day of each ISO week.
    monthly: the first trading day of each calendar month. The first day is
    always one. Same rule as `is_rebalance_session`, applied to a whole list.
    """
    grid: list[str] = []
    last: str | None = None
    for day in days:
        if is_rebalance_session(day, last, cadence):
            grid.append(day)
        last = day
    return grid


def performance_metrics(
    capital: float,
    dates: list[str],
    nav: list[float],
    benchmark_nav: list[float],
    cycles: list[CycleRecord],
    *,
    periods_per_year: float = 252,
) -> FundBacktestMetrics:
    """Closing-value performance over the full window. Sharpe is annualized
    from per-session returns by *periods_per_year*: 252 for daily sessions,
    bars-per-day × 252 for a minute fund. *dates* may be bar keys; only the
    day matters here."""
    total = nav[-1] / capital - 1

    calendar_days = (_date.fromisoformat(dates[-1][:10]) - _date.fromisoformat(dates[0][:10])).days
    years = calendar_days / 365.25
    annualized = (1 + total) ** (1 / years) - 1 if years > 0 else 0.0

    curve = np.array(nav)
    returns = curve[1:] / curve[:-1] - 1
    if len(returns) > 1 and float(returns.std(ddof=1)) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=1)) * np.sqrt(periods_per_year)
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
        n_cycles=len(cycles),
        n_orders=sum(len(r.orders) for r in cycles),
    )
