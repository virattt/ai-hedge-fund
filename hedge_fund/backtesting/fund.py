"""Daily fund replay with assessments followed by next-close execution."""

from __future__ import annotations

from datetime import date as _date
from typing import Callable, Literal

import numpy as np
from pydantic import BaseModel, Field

from hedge_fund.brokers.sim import SimBroker
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import previous_day, session_closes
from hedge_fund.fund import Fund, normalize_universe
from hedge_fund.pipeline.models import CycleRecord, DecisionRecord, PendingRunResult
from hedge_fund.pipeline.run_cycle import assess_fund, exact_marks, execute_decision


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
    n_cycles: int
    n_orders: int
    n_pending: int = 0


class FundBacktestResult(BaseModel):
    """A full backtest, serialized: the curve, the stats, and — because every
    tick is a CycleRecord — every thesis, clamp, order, and fill behind it.
    `model_dump_json()` round-trips; this is the receipts file."""

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
    records: list[CycleRecord]
    pending: list[PendingRunResult] = Field(default_factory=list)


def backtest_fund(
    fund: Fund, start: str, end: str, data_client: DataClient, universe: list[str], *,
    on_cycle: Callable[[int, int, CycleRecord], None] | None = None,
    on_valuation: Callable[[int, int, DailyValuation], None] | None = None,
) -> FundBacktestResult:
    """Replay daily marks, executing assessments only on later observed sessions.

    Callbacks receive a zero-based index, the total count, and a record.
    Executed-cycle and valuation counts are independent; the final proposal
    can remain pending without extending the requested window.
    """
    spec = fund.spec
    universe = normalize_universe(universe)
    schedule = build_schedule(data_client, spec.benchmark, start, end, spec.rebalance)
    dates = list(schedule.closes)
    broker = SimBroker(cash=spec.capital)
    records: list[CycleRecord] = []
    pending: list[PendingRunResult] = []
    due: dict[str, DecisionRecord] = {}
    nav: list[float] = []
    benchmark_nav: list[float] = []
    n_cycles = sum(day is not None for day in schedule.execution_dates.values())
    for i, session in enumerate(dates):
        if session in due:
            record = execute_decision(fund, due.pop(session), session, broker, data_client)
            records.append(record)
            if on_cycle is not None:
                on_cycle(len(records) - 1, n_cycles, record)
        held = broker.positions()
        marks = exact_marks(list(held), session, data_client)
        nav.append(broker.cash() + sum(p.shares * marks[t] for t, p in held.items()))
        benchmark_nav.append(spec.capital * schedule.closes[session] / schedule.closes[dates[0]])
        if on_valuation is not None:
            on_valuation(i, len(dates), DailyValuation(
                as_of=session, nav=nav[-1], benchmark_nav=benchmark_nav[-1],
            ))
        if session in schedule.execution_dates:
            proposal = assess_fund(fund, session, data_client, universe)
            execution = schedule.execution_dates[session]
            if execution is None:
                pending.append(PendingRunResult(
                    fund=spec.name, as_of=session, proposal=proposal,
                    reason="No subsequent completed benchmark session exists inside the backtest window.",
                ))
            else:
                due[execution] = proposal
    return FundBacktestResult(
        fund=spec.name, start=dates[0], end=dates[-1], rebalance=spec.rebalance,
        benchmark=spec.benchmark, universe=universe, capital=spec.capital,
        dates=dates, nav=nav, benchmark_nav=benchmark_nav,
        metrics=performance_metrics(spec.capital, dates, nav, benchmark_nav, records, len(pending)),
        records=records, pending=pending,
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


def performance_metrics(
    capital: float,
    dates: list[str],
    nav: list[float],
    benchmark_nav: list[float],
    records: list[CycleRecord],
    n_pending: int = 0,
) -> FundBacktestMetrics:
    """Closing-value performance over the full window, with daily-return Sharpe."""
    total = nav[-1] / capital - 1

    calendar_days = (_date.fromisoformat(dates[-1]) - _date.fromisoformat(dates[0])).days
    years = calendar_days / 365.25
    annualized = (1 + total) ** (1 / years) - 1 if years > 0 else 0.0

    curve = np.array(nav)
    returns = curve[1:] / curve[:-1] - 1
    if len(returns) > 1 and float(returns.std(ddof=1)) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=1)) * np.sqrt(252)
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
        n_cycles=len(records),
        n_pending=n_pending,
        n_orders=sum(len(r.orders) for r in records),
    )
