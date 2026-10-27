"""advance — one session of the fund, the same code path in every mode.

    reconcile -> execute the pending decision -> mark the book -> assess

This is the fund's daily unit of work. A backtest is `advance` looped over
historical sessions with an in-memory FundState and a SimBroker; paper
trading is `advance` called once per completed session against a FundState
replayed from the ledger and a PaperBroker. Only the clock, the broker, and
where the state lives change — the sequence never does.

Timing, chosen deliberately:
- A decision assessed at session T's close is executed at the NEXT
  advanced session's close (T+1). It rides on T's SessionRecord as
  `decision`; T+1's record carries the resulting CycleRecord as `executed`.
  Nothing is ever assessed and executed against the same close.
- Whether a session is a rebalance session is decided from the session and
  the previous one only (first session of each period), never from what
  comes after — the rule must be computable on a live tick, so backtest and
  paper agree by construction.
- Before anything touches the market, the broker's book is reconciled
  against the state the ledger implies. A mismatch is not repaired; it is
  raised, because the two books disagreeing means something upstream lied.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import date as _date
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version
from math import isclose
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from hedge_fund.brokers.protocol import Broker
from hedge_fund.data.bars import is_intraday
from hedge_fund.data.protocol import DataClient
from hedge_fund.fund import Cadence, Fund, FundSpec, normalize_universe
from hedge_fund.llm import DEFAULT_MODEL
from hedge_fund.pipeline.clock import Clock, clock_for
from hedge_fund.pipeline.models import CycleRecord, DecisionRecord
from hedge_fund.pipeline.stages import assess_fund, execute_decision
from hedge_fund.signals import LLMAgent

__all__ = ["Cadence"]  # re-exported for callers that typed against the engine

# Cash is compared to the cent: fills are whole shares at a float price, so
# two honest books can differ by float noise, never by money.
_CASH_TOLERANCE = 0.01


class FundHalted(RuntimeError):
    """The fund's kill switch is set; nothing trades until it is cleared."""


class BookMismatch(RuntimeError):
    """The broker's book and the ledger's book disagree."""


class FundState(BaseModel):
    """What the fund carries between sessions. Derived by folding
    `next_state` over the ledger; never edited by hand."""

    positions: dict[str, int] = Field(default_factory=dict)  # signed shares
    cash: float
    last_session: str | None = None
    pending: DecisionRecord | None = None       # assessed, awaiting execution
    prev_hash: str | None = None                # hash of the last record
    halted: str | None = None                   # reason, when the kill switch is set

    @classmethod
    def initial(cls, capital: float) -> FundState:
        return cls(cash=capital)


class SessionRecord(BaseModel):
    """One session of the fund, fully serialized: the book after the close,
    the decision executed at this close (if any), and the decision made at
    this close (if any). Hash-chained to the record before it."""

    schema_version: Literal[2] = 2
    fund: str
    session: str
    universe: list[str]
    nav: float                          # cash + sum(shares * mark) at this close
    cash: float
    positions: dict[str, int]           # signed shares after this session
    marks: dict[str, float]             # closes used to value the book
    benchmark: str
    benchmark_close: float
    rebalance: bool                     # was this a rebalance session?
    executed: CycleRecord | None = None     # the prior decision, executed here
    decision: DecisionRecord | None = None  # assessed here, executed next session
    prev_hash: str | None = None
    hash: str = ""
    code_version: str
    mandate_hash: str
    llm_model: str | None = None
    # When the marks are live prints (a minute fund), the moment of each
    # ticker's print — so a name that last traded an hour ago is visible.
    snapshot_times: dict[str, str] | None = None

    def compute_hash(self) -> str:
        # A record without print times hashes exactly as it did before the
        # field existed: every ledger written until then must still verify.
        exclude = {"hash"} | ({"snapshot_times"} if self.snapshot_times is None else set())
        payload = self.model_dump_json(exclude=exclude)
        return hashlib.sha256(payload.encode()).hexdigest()

    def price_at(self, ticker: str) -> float | None:
        """The best price this record has for *ticker* at its session: the
        exact execution mark, then the exact valuation mark, then, for a
        daily session only, the assessment's close. A bar's record never
        answers with a daily close: the assessment marks a minute fund at
        the day's close, the same number for every bar of the day."""
        if self.executed is not None and ticker in self.executed.marks:
            return self.executed.marks[ticker]
        if ticker in self.marks:
            return self.marks[ticker]
        if self.decision is not None and not is_intraday(self.session) and ticker in self.decision.marks:
            return self.decision.marks[ticker]
        return None


def advance(
    fund: Fund,
    state: FundState,
    session: str,
    broker: Broker,
    data_client: DataClient,
    universe: list[str],
    clock: Clock | None = None,
) -> SessionRecord:
    """Advance *fund* through one completed *session*: a date (YYYY-MM-DD)
    for a daily/weekly/monthly fund, a bar (YYYY-MM-DDTHH:MM:SS, New York)
    for a minute fund.

    The caller owns the state: fold the returned record into it with
    `next_state` before advancing again. *clock* says what "complete" and
    "the price at a session" mean; without one, the mandate's own (daily
    closes, or historical minute bars). Raises FundHalted if the kill
    switch is set, BookMismatch if the broker disagrees with the state, and
    ValueError for a session that is out of order or not yet complete.
    """
    spec = fund.spec
    clock = clock or clock_for(spec, data_client)
    if state.halted is not None:
        raise FundHalted(f"{spec.name} is halted: {state.halted}")
    if state.last_session is not None and session <= state.last_session:
        raise ValueError(
            f"{spec.name}: session {session} is not after the last recorded "
            f"session {state.last_session}"
        )
    if not clock.is_complete(session):
        raise ValueError(f"{spec.name}: session {session} is not complete yet")
    universe = normalize_universe(universe)
    reconcile(state, broker, spec.name)

    executed: CycleRecord | None = None
    if state.pending is not None:
        executed = execute_decision(fund, state.pending, session, broker, data_client, clock)

    held = broker.positions()
    marked = clock.marks([*held, spec.benchmark], session)
    marks = {t: marked.prices[t] for t in sorted(held)}
    cash = broker.cash()
    positions = {t: p.shares for t, p in sorted(held.items())}
    nav = cash + sum(shares * marks[t] for t, shares in positions.items())

    rebalance = is_rebalance_session(session, state.last_session, spec.rebalance)
    decision = assess_fund(fund, session, data_client, universe, clock) if rebalance else None

    record = SessionRecord(
        fund=spec.name,
        session=session,
        universe=universe,
        nav=nav,
        cash=cash,
        positions=positions,
        marks=marks,
        benchmark=spec.benchmark,
        benchmark_close=marked.prices[spec.benchmark],
        rebalance=rebalance,
        executed=executed,
        decision=decision,
        prev_hash=state.prev_hash,
        code_version=code_version(),
        mandate_hash=mandate_hash(spec),
        llm_model=_llm_model(fund),
        snapshot_times=marked.times,
    )
    record.hash = record.compute_hash()
    return record


def next_state(state: FundState, record: SessionRecord) -> FundState:
    """The state after *record*. Pure; the ledger replays with it."""
    return FundState(
        positions=dict(record.positions),
        cash=record.cash,
        last_session=record.session,
        pending=record.decision,
        prev_hash=record.hash,
        halted=state.halted,
    )


def reconcile(state: FundState, broker: Broker, name: str) -> None:
    """Raise BookMismatch unless the broker holds exactly what the state says."""
    held = {t: p.shares for t, p in broker.positions().items() if p.shares != 0}
    expected = {t: s for t, s in state.positions.items() if s != 0}
    problems: list[str] = []
    for ticker in sorted(set(held) | set(expected)):
        if held.get(ticker, 0) != expected.get(ticker, 0):
            problems.append(
                f"{ticker}: broker {held.get(ticker, 0):+d} vs ledger {expected.get(ticker, 0):+d}"
            )
    if not isclose(broker.cash(), state.cash, rel_tol=0, abs_tol=_CASH_TOLERANCE):
        problems.append(f"cash: broker {broker.cash():,.2f} vs ledger {state.cash:,.2f}")
    if problems:
        raise BookMismatch(f"{name}: broker and ledger disagree — " + "; ".join(problems))


def is_rebalance_session(session: str, last_session: str | None, cadence: str) -> bool:
    """First session of each period: minute is every bar and daily every
    session; weekly is the first session of an ISO week; monthly the first
    of a calendar month. The fund's first session is always a rebalance
    session."""
    if cadence not in ("minute", "daily", "weekly", "monthly"):
        raise ValueError(f"unknown rebalance cadence {cadence!r}")
    if cadence in ("minute", "daily") or last_session is None:
        return True
    return _period(session, cadence) != _period(last_session, cadence)


def _period(day: str, cadence: str) -> tuple[int, int]:
    d = _date.fromisoformat(day[:10])
    if cadence == "weekly":
        iso = d.isocalendar()
        return (iso[0], iso[1])
    return (d.year, d.month)


def mandate_hash(spec: FundSpec) -> str:
    return hashlib.sha256(spec.model_dump_json().encode()).hexdigest()


@lru_cache(maxsize=1)
def code_version() -> str:
    """Package version, plus the git commit when running from a checkout."""
    try:
        version = _version("aihf")
    except PackageNotFoundError:
        version = "dev"
    root = Path(__file__).resolve().parents[2]
    try:
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        sha = ""
    return f"{version}+{sha}" if sha else version


def _llm_model(fund: Fund) -> str | None:
    """The LLM the investor agents reason with, if the fund staffs any."""
    if any(isinstance(m, LLMAgent) for _, staff in fund.strategies for m in staff):
        return os.environ.get("HEDGE_FUND_LLM_MODEL") or DEFAULT_MODEL
    return None
