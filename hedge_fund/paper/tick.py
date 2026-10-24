"""tick — advance a paper fund by exactly one session.

This is what a human, a scheduler, or the runner calls when a session is
due:

    aihf paper tick <name>        # cron, launchd, or a human

It loads the fund, replays the ledger into its state, works out the next
session the fund owes, advances it, and appends the record. Calling it
twice is harmless: the second call finds nothing due. For a daily fund the
next session is the oldest unrecorded completed close: a missed day is
never skipped, and catching up after a week away takes a week of ticks,
each honest. For a minute fund it is the latest bar boundary that has
passed, at prints taken now: a bar is never back-filled, so a late tick
records the print it took and when it took it.

Any failure inside `advance` halts the fund. Cron retrying into a broken
book is the failure mode this exists to prevent; a human clears the halt.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.data.bars import current_bar, is_intraday, is_last_bar, next_bar, previous_bar, session_date
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import completed_through, NEW_YORK, previous_day, session_closes
from hedge_fund.fund import Fund, FundSpec, TradingWindow
from hedge_fund.paper.deployed import BROKER_FILE, load_deployed
from hedge_fund.paper.ledger import Ledger
from hedge_fund.pipeline.clock import Clock, LiveClock, Marked
from hedge_fund.pipeline.session import advance, FundHalted, FundState, is_rebalance_session, next_state, SessionRecord

# A fresh fund starts at the most recent completed session; this is how far
# back to look for one (covers a long weekend plus a holiday cluster).
_FRESH_LOOKBACK_DAYS = 14


class NothingDue(RuntimeError):
    """Every session that can be run is already recorded."""


class RecordedClock:
    """A bar run again at the prices it saw. A print cannot be taken twice,
    so a redo of a bar serves the marks its record kept — the book's names,
    the benchmark, and whatever the executed decision was sized at. A name
    none of those cover has no honest price, and the redo says so."""

    def __init__(self, record: SessionRecord, interval_seconds: int, window: TradingWindow) -> None:
        self._record = record
        self._interval = interval_seconds
        self._window = window
        self._prices = {record.benchmark: record.benchmark_close, **record.marks}
        if record.executed is not None:
            self._prices = {**record.executed.marks, **self._prices}
        self._times = dict(record.snapshot_times or {})

    def is_complete(self, session: str) -> bool:
        return session <= self._record.session

    def previous(self, session: str) -> str:
        return previous_bar(session, self._interval, self._window)

    def session_date(self, session: str) -> str:
        return session_date(session)

    def marks(self, tickers: list[str], session: str) -> Marked:
        if session != self._record.session:
            raise ValueError(f"{session}: only {self._record.session} can be run again at recorded prices")
        missing = sorted(set(tickers) - set(self._prices))
        if missing:
            raise ValueError(
                f"{', '.join(missing)}: no recorded print at {session}; a bar can only be run "
                "again at the prices it saw"
            )
        return Marked(
            prices={t: self._prices[t] for t in sorted(set(tickers))},
            times={t: self._times[t] for t in sorted(set(tickers)) if t in self._times} or None,
        )


def next_session(
    data_client: DataClient, spec: FundSpec, last_session: str | None,
    *, now: Callable[[], datetime] | None = None,
) -> str | None:
    """The next session the fund owes, or None when nothing is due yet.

    Daily cadences: the first benchmark session after *last_session*, or,
    for a fund that has never ticked, the most recent completed one. Minute
    cadence: the latest bar boundary at or before now, if it is newer than
    *last_session*; no network, the bar's prints are taken when it runs.
    """
    moment = now() if now is not None else None  # None: the engine's own clock
    if spec.is_intraday:
        bar = current_bar(moment or datetime.now(NEW_YORK), spec.interval_seconds, spec.window)
        if bar is None or (last_session is not None and bar <= last_session):
            return None
        return bar
    end = completed_through(moment)
    if last_session is None:
        start = (_date.fromisoformat(end) - timedelta(days=_FRESH_LOOKBACK_DAYS)).isoformat()
        closes = session_closes(data_client, spec.benchmark, start, end)
        return max(closes) if closes else None
    start = (_date.fromisoformat(session_date(last_session)) + timedelta(days=1)).isoformat()
    closes = session_closes(data_client, spec.benchmark, start, end)
    return min(closes) if closes else None


def following_session(spec: FundSpec, after: str | None, now: datetime) -> str:
    """When the session after the current one arrives, as a short phrase
    for a human: the next bar boundary, or the next weekday's close."""
    if spec.is_intraday:
        upcoming = next_bar(now, spec.interval_seconds, spec.window)
        same_day = upcoming.date() == now.astimezone(NEW_YORK).date()
        return upcoming.strftime("%H:%M:%S ET" if same_day else "%a %H:%M:%S ET")
    day = _date.fromisoformat(session_date(after)) if after else now.astimezone(NEW_YORK).date()
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return f"{day.isoformat()} close"


def previous_session(session: str, spec: FundSpec) -> str:
    """The session before *session* on the fund's own grid: the bar before
    a bar, the calendar day before a date (what `execute_decision` uses as
    the refresh cutoff)."""
    if is_intraday(session):
        return previous_bar(session, spec.interval_seconds, spec.window)
    return previous_day(session)


def assessment_dates(state: FundState, session: str, spec: FundSpec) -> list[str]:
    """The sessions the analysts are asked about when *session* is run from
    *state*: the session before it, to refresh a pending decision made
    earlier than that (`execute_decision` sizes from the refreshed views),
    and *session* itself when it opens a rebalance period (`advance` then
    makes a new decision)."""
    dates: list[str] = []
    before = previous_session(session, spec)
    if state.pending is not None and before != state.pending.as_of:
        dates.append(before)
    if is_rebalance_session(session, state.last_session, spec.rebalance):
        dates.append(session)
    return dates


def tick(
    directory: str | Path,
    data_client: DataClient,
    *,
    session: str | None = None,
    build_fund: Callable[[FundSpec], Fund] | None = None,
    now: Callable[[], datetime] | None = None,
) -> SessionRecord:
    """Advance the paper fund in *directory* by one session and record it.

    *session* is a backfill override: it must be the next unrecorded
    session. Passing a session that is already recorded returns its record
    unchanged (idempotent). Raises NothingDue when no session can be run
    yet (no completed close after the last one; no bar boundary passed; the
    benchmark has not printed today), FundHalted when the kill switch is
    set. *now* is the clock; tests inject it.
    """
    directory = Path(directory)
    deployed = load_deployed(directory)
    spec = deployed.spec
    ledger = Ledger(directory)
    if session is not None and session in ledger.sessions():
        return ledger.read(session)
    state = ledger.replay(spec.capital)
    if state.halted is not None:
        raise FundHalted(f"{deployed.name} is halted: {state.halted}")

    due = next_session(data_client, spec, state.last_session, now=now)
    now = now or (lambda: datetime.now(NEW_YORK))
    if due is None:
        after = f"after {state.last_session}" if state.last_session else "yet"
        what = "bar" if spec.is_intraday else f"completed {spec.benchmark} session"
        raise NothingDue(f"{deployed.name}: no {what} {after}; next {following_session(spec, state.last_session, now())}")
    if session is not None and session != due:
        raise ValueError(
            f"{deployed.name}: session {session} is not the next unrecorded session ({due})"
        )
    clock = None
    if spec.is_intraday:
        # The benchmark's print says whether the market is trading today; a
        # bar on a holiday is nothing due, not a failure. A held name's own
        # missing print is a failure of the bar and halts inside `_run`.
        clock = LiveClock(data_client, spec.interval_seconds, spec.window, now=now)
        benchmark = clock.observe([spec.benchmark], due)[spec.benchmark]
        if print_day(benchmark.time) < session_date(due):
            raise NothingDue(
                f"{deployed.name}: {spec.benchmark} has not printed today (market closed); "
                f"next {following_session(spec, state.last_session, now())}"
            )
    return _run(directory, deployed, ledger, state, due, data_client, build_fund, clock=clock)


def print_day(time: str) -> str:
    """The New York date a print's timestamp falls on."""
    return datetime.fromisoformat(time.replace("Z", "+00:00")).astimezone(NEW_YORK).date().isoformat()


def redo(
    directory: str | Path,
    data_client: DataClient,
    *,
    build_fund: Callable[[FundSpec], Fund] | None = None,
) -> SessionRecord:
    """Run the latest recorded session again and replace its record.

    For when the fund already ran today and you want it to look again:
    the analysts are asked afresh, the book is sized afresh, all at the same
    close. The old record leaves the chain for ledger/superseded/ (a redo is
    an event, not an erasure), the broker's book is put back to where it
    stood going into that session, and the session is advanced as if for
    the first time. Raises NothingDue when nothing has been recorded yet,
    FundHalted when the kill switch is set.
    """
    directory = Path(directory)
    deployed = load_deployed(directory)
    ledger = Ledger(directory)
    state = ledger.replay(deployed.spec.capital)  # verifies the whole chain first
    if state.halted is not None:
        raise FundHalted(f"{deployed.name} is halted: {state.halted}")
    if state.last_session is None:
        raise NothingDue(f"{deployed.name}: no session recorded yet, nothing to run again")

    before = ledger.replay(deployed.spec.capital, before=state.last_session)
    superseded = ledger.rewind()
    PaperBroker.restore(directory / BROKER_FILE, before.cash, before.positions, deployed.spec.costs)
    ledger.log_event("redo", session=superseded.session, superseded=superseded.hash)
    clock = None
    if deployed.spec.is_intraday:  # a bar's prints are gone; run it at the ones it kept
        clock = RecordedClock(superseded, deployed.spec.interval_seconds, deployed.spec.window)
    return _run(directory, deployed, ledger, before, superseded.session, data_client, build_fund, clock=clock)


def _run(
    directory: Path,
    deployed,
    ledger: Ledger,
    state,
    session: str,
    data_client: DataClient,
    build_fund: Callable[[FundSpec], Fund] | None,
    *,
    clock: Clock | None = None,
    fund: Fund | None = None,
) -> SessionRecord:
    """Advance one session from *state* and record it, halting on failure.
    *fund* lets a long-running caller keep one Fund (and its analysts'
    caches) across sessions instead of staffing a new one each time. A
    minute fund's closing bar also checkpoints the day, so tomorrow's
    replay starts from tonight."""
    broker = PaperBroker(directory / BROKER_FILE, deployed.spec.costs)
    fund = fund or (build_fund or Fund)(deployed.spec)
    try:
        record = advance(fund, state, session, broker, data_client, deployed.universe, clock)
        ledger.append(record)
    except FundHalted:
        raise
    except Exception as exc:
        reason = f"tick {session} failed: {type(exc).__name__}: {exc}"
        ledger.log_event("tick_failed", session=session, error=f"{type(exc).__name__}: {exc}")
        ledger.halt(reason)
        raise
    ledger.log_event(
        "tick", session=session, nav=record.nav,
        executed=record.executed is not None, decided=record.decision is not None,
    )
    if is_intraday(session) and is_last_bar(session, deployed.spec.window):
        ledger.checkpoint(next_state(state, record))
    return record
