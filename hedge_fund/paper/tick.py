"""tick — advance a paper fund by exactly one session.

This is what the scheduler calls after each close:

    aihf paper tick <name>        # cron, launchd, or a human

It loads the fund, replays the ledger into its state, works out the next
unrecorded benchmark session, advances it, and appends the record. Calling
it twice is harmless: the second call finds nothing due. A missed day is
never skipped — the next tick advances the oldest unrecorded session, and
catching up after a week away takes a week of ticks, each honest.

Any failure inside `advance` halts the fund. Cron retrying into a broken
book is the failure mode this exists to prevent; a human clears the halt.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from pathlib import Path
from typing import Callable

from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import completed_through, session_closes
from hedge_fund.fund import Fund, FundSpec
from hedge_fund.paper.deployed import BROKER_FILE, load_deployed
from hedge_fund.paper.ledger import Ledger
from hedge_fund.pipeline.session import advance, FundHalted, SessionRecord

# A fresh fund starts at the most recent completed session; this is how far
# back to look for one (covers a long weekend plus a holiday cluster).
_FRESH_LOOKBACK_DAYS = 14


class NothingDue(RuntimeError):
    """Every completed session is already recorded."""


def next_session(data_client: DataClient, benchmark: str, last_session: str | None) -> str | None:
    """The next session the fund owes: the first benchmark session after
    *last_session*, or — for a fund that has never ticked — the most recent
    completed one. None when nothing is due yet."""
    end = completed_through()
    if last_session is None:
        start = (_date.fromisoformat(end) - timedelta(days=_FRESH_LOOKBACK_DAYS)).isoformat()
        closes = session_closes(data_client, benchmark, start, end)
        return max(closes) if closes else None
    start = (_date.fromisoformat(last_session) + timedelta(days=1)).isoformat()
    closes = session_closes(data_client, benchmark, start, end)
    return min(closes) if closes else None


def tick(
    directory: str | Path,
    data_client: DataClient,
    *,
    session: str | None = None,
    build_fund: Callable[[FundSpec], Fund] | None = None,
) -> SessionRecord:
    """Advance the paper fund in *directory* by one session and record it.

    *session* is a backfill override: it must be the next unrecorded
    session. Passing a session that is already recorded returns its record
    unchanged (idempotent). Raises NothingDue when no completed session
    follows the last recorded one, FundHalted when the kill switch is set.
    """
    directory = Path(directory)
    deployed = load_deployed(directory)
    ledger = Ledger(directory)
    if session is not None and session in ledger.sessions():
        return ledger.read(session)
    state = ledger.replay(deployed.spec.capital)
    if state.halted is not None:
        raise FundHalted(f"{deployed.name} is halted: {state.halted}")

    due = next_session(data_client, deployed.spec.benchmark, state.last_session)
    if due is None:
        after = f"after {state.last_session}" if state.last_session else "yet"
        raise NothingDue(f"{deployed.name}: no completed {deployed.spec.benchmark} session {after}")
    if session is not None and session != due:
        raise ValueError(
            f"{deployed.name}: session {session} is not the next unrecorded session ({due})"
        )
    return _run(directory, deployed, ledger, state, due, data_client, build_fund)


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
    PaperBroker.restore(directory / BROKER_FILE, before.cash, before.positions)
    ledger.log_event("redo", session=superseded.session, superseded=superseded.hash)
    return _run(directory, deployed, ledger, before, superseded.session, data_client, build_fund)


def _run(
    directory: Path,
    deployed,
    ledger: Ledger,
    state,
    session: str,
    data_client: DataClient,
    build_fund: Callable[[FundSpec], Fund] | None,
) -> SessionRecord:
    """Advance one session from *state* and record it, halting on failure."""
    broker = PaperBroker(directory / BROKER_FILE)
    fund = (build_fund or Fund)(deployed.spec)
    try:
        record = advance(fund, state, session, broker, data_client, deployed.universe)
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
    return record
