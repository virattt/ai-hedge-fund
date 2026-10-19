"""run — the loop a minute fund lives in.

    aihf paper run <name>

A daily fund is advanced by a tick after each close. A minute fund has a bar
every interval inside its trading window, so something has to be awake:
this loop sleeps to the next boundary, takes one print per name there,
advances the fund through that bar with `_run` (the same path a tick
takes), and goes back to sleep. After the window's last bar it writes the
day's checkpoint so tomorrow's replay starts from tonight.

What it does with time it was not awake for: nothing. On start, if the
current bar is not the one after the last recorded bar, the span between
is logged as a `gap` event and the fund picks up at the current bar; the
pending decision, if any, is refreshed at the bar before execution by
`execute_decision` itself (its cutoff is no longer the bar it was made at).
No bar is ever back-filled with prices the fund did not see.

A bar whose prints cannot be taken (the API is down, or the benchmark
has not printed today: a holiday, or a window that opens before the first
trade) is skipped with a `gap` event, not a halt. A failure inside
`advance`, a held name with no print included, halts the fund exactly as
a failed tick does.
"""

from __future__ import annotations

import os
import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from hedge_fund.data.bars import (
    bar_time,
    bars_between,
    is_last_bar,
    next_bar,
    session_date,
    to_key,
)
from hedge_fund.data.client import FDClientError
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.fund import Fund, FundSpec
from hedge_fund.paper.deployed import load_deployed
from hedge_fund.paper.ledger import Ledger
from hedge_fund.paper.tick import _run, MinuteFund
from hedge_fund.pipeline.clock import LiveClock
from hedge_fund.pipeline.session import FundHalted, next_state, SessionRecord

PID_FILE = "runner.pid"
_LATE_SECONDS = 60  # how long after a boundary its prints still count as that bar's


def run(
    directory: str | Path,
    data_client: DataClient,
    *,
    stop: threading.Event | None = None,
    build_fund: Callable[[FundSpec], Fund] | None = None,
    on_record: Callable[[SessionRecord], None] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Advance the minute fund in *directory* bar by bar until *stop* is set.

    *now* and *sleep* are the clock and the wait; tests inject both. The
    default wait is `stop.wait`, so a stop lands within the second. Raises
    MinuteFund for a daily fund and FundHalted when the kill switch is set
    (on start, or after a bar fails).
    """
    directory = Path(directory)
    deployed = load_deployed(directory)
    spec = deployed.spec
    if not spec.is_intraday:
        raise MinuteFund(f"{deployed.name} is a {spec.rebalance} fund: advance it with `aihf paper tick`")
    stop = stop or threading.Event()
    now = now or (lambda: datetime.now(NEW_YORK))
    sleep = sleep or stop.wait
    ledger = Ledger(directory)
    clock = LiveClock(data_client, spec.interval_seconds, spec.window, now=now)
    fund = (build_fund or Fund)(spec)  # once: the analysts' caches live across bars
    closed_day: str | None = None      # the day already logged as not trading

    def event(kind: str, **fields) -> None:
        ledger.log_event(kind, **fields)
        if on_event is not None:
            on_event(kind, fields)

    while not stop.is_set():
        state = ledger.replay(spec.capital)
        if state.halted is not None:
            raise FundHalted(f"{deployed.name} is halted: {state.halted}")
        bar = clock.current()
        if bar is None or (state.last_session is not None and bar <= state.last_session):
            _wait_for(next_bar(now(), spec.interval_seconds, spec.window), now, sleep)
            continue
        if (now() - bar_time(bar)).total_seconds() > max(spec.interval_seconds, _LATE_SECONDS):
            # Too late to call this the bar's print (an evening start would
            # otherwise mark today's close at tonight's price): the next bar
            # is the first honest one, and the gap is logged when it runs.
            _wait_for(next_bar(now(), spec.interval_seconds, spec.window), now, sleep)
            continue

        # The benchmark's print says whether the market is trading today. A
        # name's own missing print is a failure of the bar, and halts inside
        # `_run` the way a daily tick with a missing close does.
        try:
            benchmark = clock.observe([spec.benchmark], bar)[spec.benchmark]
        except FDClientError as exc:
            event("gap", **{"from": state.last_session, "to": bar, "reason": f"no prints: {exc}"})
            _wait_for(next_bar(now(), spec.interval_seconds, spec.window), now, sleep)
            continue
        if _print_day(benchmark.time) < session_date(bar):
            if closed_day != session_date(bar):  # a holiday, or the market has not opened yet
                closed_day = session_date(bar)
                event("gap", **{"from": state.last_session, "to": bar,
                                "reason": f"{spec.benchmark} has not printed today; market closed"})
            _wait_for(next_bar(now(), spec.interval_seconds, spec.window), now, sleep)
            continue

        if state.last_session is not None:
            expected = to_key(next_bar(bar_time(state.last_session), spec.interval_seconds, spec.window))
            if bar != expected:
                event("gap", **{"from": state.last_session, "to": bar,
                                "bars_skipped": bars_between(state.last_session, bar, spec.interval_seconds, spec.window)})

        record = _run(directory, deployed, ledger, state, bar, data_client, build_fund, clock=clock, fund=fund)
        if on_record is not None:
            on_record(record)
        if is_last_bar(bar, spec.window):
            ledger.checkpoint(next_state(state, record))
        if not stop.is_set():
            _wait_for(next_bar(now(), spec.interval_seconds, spec.window), now, sleep)


def _wait_for(moment: datetime, now: Callable[[], datetime], sleep: Callable[[float], None]) -> None:
    seconds = (moment - now()).total_seconds()
    if seconds > 0:
        sleep(seconds)


def _print_day(time: str) -> str:
    return datetime.fromisoformat(time.replace("Z", "+00:00")).astimezone(NEW_YORK).date().isoformat()


# ---------------------------------------------------------------------------
# The process around the loop
# ---------------------------------------------------------------------------

def serve(
    directory: str | Path,
    data_client: DataClient,
    *,
    build_fund: Callable[[FundSpec], Fund] | None = None,
    on_record: Callable[[SessionRecord], None] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> None:
    """`run` as a process: one per fund, found by its pid file, stopped by
    SIGTERM or SIGINT after the bar in flight. Refuses to start twice."""
    directory = Path(directory)
    if is_running(directory):
        raise RuntimeError(f"{directory.name} is already running (pid {_read_pid(directory)})")
    stop = threading.Event()
    previous = {s: signal.signal(s, lambda *_: stop.set()) for s in (signal.SIGTERM, signal.SIGINT)}
    (directory / PID_FILE).write_text(str(os.getpid()))
    try:
        run(directory, data_client, stop=stop, build_fund=build_fund, on_record=on_record, on_event=on_event)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if _read_pid(directory) == os.getpid():
            (directory / PID_FILE).unlink(missing_ok=True)


def is_running(directory: str | Path) -> bool:
    """Whether a runner holds this fund: its pid file names a live process."""
    pid = _read_pid(directory)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_runner(directory: str | Path) -> bool:
    """Ask the fund's runner to stop after its current bar. False if none."""
    pid = _read_pid(directory)
    if pid is None or not is_running(directory):
        return False
    os.kill(pid, signal.SIGTERM)
    return True


def _read_pid(directory: str | Path) -> int | None:
    path = Path(directory) / PID_FILE
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None
