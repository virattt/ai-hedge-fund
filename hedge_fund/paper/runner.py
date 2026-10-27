"""run — the loop a paper fund lives in when nobody is watching.

    aihf paper run <name>

Any fund can be advanced a session at a time by hand (the app, `aihf paper
tick`). This loop does the same thing unattended: it sleeps until the fund's
next session is due, advances it through `_run` (the path a tick takes),
and goes back to sleep. The cadence decides what "due" means.

A daily fund's session is a completed close, which under the engine's rule
is any date before today in New York. The loop wakes just after midnight,
advances every session that has become due since it last looked, oldest
first, and sleeps again; a missed week is caught up one honest session at
a time, exactly as a week of ticks would.

A minute fund's session is a bar boundary, and its prints exist only at the
boundary. The loop wakes at each one, takes one print per name there, and
advances the bar. What it does with time it was not awake for: nothing. On
start, if the current bar is not the one after the last recorded bar, the
span between is logged as a `gap` event and the fund picks up at the
current bar; the pending decision, if any, is refreshed at the bar before
execution by `execute_decision` itself. No bar is ever back-filled with
prices the fund did not see, and a boundary the loop reaches too late to
call its own is left for the next.

A bar whose prints cannot be taken (the API is down, or the benchmark has
not printed today: a holiday, or a window that opens before the first
trade) is skipped with a `gap` event, not a halt. A failure inside
`advance`, a held name with no print included, halts the fund exactly as a
failed tick does.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Callable

from hedge_fund.data.bars import (
    bar_time,
    bars_between,
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
from hedge_fund.paper.tick import _run, next_session, print_day
from hedge_fund.pipeline.clock import LiveClock
from hedge_fund.pipeline.session import FundHalted, SessionRecord

PID_FILE = "runner.pid"
_LATE_SECONDS = 60      # how long after a boundary its prints still count as that bar's
_DAY_TURNS = time(0, 5)  # when a daily fund's loop first looks for yesterday's close
_DAY_POLL = 3600         # ...and how often it looks again until the close has landed


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
    """Advance the fund in *directory* session by session until *stop* is set.

    *now* and *sleep* are the clock and the wait; tests inject both. The
    default wait is `stop.wait`, so a stop lands within the second. Raises
    FundHalted when the kill switch is set (on start, or after a session
    fails).
    """
    directory = Path(directory)
    deployed = load_deployed(directory)
    stop = stop or threading.Event()
    now = now or (lambda: datetime.now(NEW_YORK))
    sleep = sleep or stop.wait
    fund = (build_fund or Fund)(deployed.spec)  # once: the analysts' caches live across sessions
    loop = _run_bars if deployed.spec.is_intraday else _run_days
    loop(directory, deployed, data_client, fund, stop=stop, build_fund=build_fund,
         on_record=on_record, on_event=on_event, now=now, sleep=sleep)


def _run_days(directory, deployed, data_client, fund, *, stop, build_fund, on_record, on_event, now, sleep):
    """A daily fund: every session that has become due, oldest first, then
    sleep to the next turn of the day."""
    spec = deployed.spec
    ledger = Ledger(directory)
    while not stop.is_set():
        state = ledger.replay(spec.capital)
        if state.halted is not None:
            raise FundHalted(f"{deployed.name} is halted: {state.halted}")
        due = next_session(data_client, spec, state.last_session, now=now)
        if due is None:
            _wait_for(_next_look(now()), now, sleep)
            continue
        record = _run(directory, deployed, ledger, state, due, data_client, build_fund, fund=fund)
        if on_record is not None:
            on_record(record)


def _next_look(now: datetime) -> datetime:
    """When a daily loop looks again: just after the next New York midnight,
    or in an hour if the day has turned and the close has not landed yet."""
    local = now.astimezone(NEW_YORK)
    turn = datetime.combine(local.date(), _DAY_TURNS, tzinfo=NEW_YORK)
    if local < turn:
        return turn
    return min(turn + timedelta(days=1), local + timedelta(seconds=_DAY_POLL))


def _run_bars(directory, deployed, data_client, fund, *, stop, build_fund, on_record, on_event, now, sleep):
    """A minute fund: one print per name at each boundary, the bar advanced
    there, gaps logged for the boundaries the loop was not awake for."""
    spec = deployed.spec
    ledger = Ledger(directory)
    clock = LiveClock(data_client, spec.interval_seconds, spec.window, now=now)
    closed_day: str | None = None  # the day already logged as not trading

    def event(kind: str, **fields) -> None:
        ledger.log_event(kind, **fields)
        if on_event is not None:
            on_event(kind, fields)

    while not stop.is_set():
        state = ledger.replay(spec.capital)
        if state.halted is not None:
            raise FundHalted(f"{deployed.name} is halted: {state.halted}")
        bar = next_session(data_client, spec, state.last_session, now=now)
        if bar is None:
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
        if print_day(benchmark.time) < session_date(bar):
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
        if not stop.is_set():
            _wait_for(next_bar(now(), spec.interval_seconds, spec.window), now, sleep)


def _wait_for(moment: datetime, now: Callable[[], datetime], sleep: Callable[[float], None]) -> None:
    seconds = (moment - now()).total_seconds()
    if seconds > 0:
        sleep(seconds)


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


_RUNNER_LOG = "runner.log"  # where a runner started from the app writes its console


def spawn_runner(directory: Path) -> int:
    """Start `aihf paper run <name>` as its own session so it survives the
    app closing; its console goes to runner.log in the fund directory. The
    runner writes runner.pid itself once it is up. Returns the child's pid."""
    log = (directory / _RUNNER_LOG).open("a")
    with log:
        child = subprocess.Popen(
            [sys.executable, "-m", "hedge_fund.run", "paper", "run", directory.name],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, cwd=str(directory),
        )
    return child.pid


def _read_pid(directory: str | Path) -> int | None:
    path = Path(directory) / PID_FILE
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None
