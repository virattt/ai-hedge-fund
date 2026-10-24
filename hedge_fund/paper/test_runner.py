"""run — the unattended loop at both cadences, driven by a fake clock and
canned prints; and tick on a bar, the same session by hand."""

import os
import signal
import threading
from datetime import datetime, timedelta

import pytest

from hedge_fund.backtesting.test_fund import FakeDataClient, SERIES
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.fund import Fund, FundSpec
from hedge_fund.paper import deploy, is_running, Ledger, NothingDue, PID_FILE, redo, run, serve, stop_runner, tick
from hedge_fund.paper.test_tick import build_fund
from hedge_fund.pipeline.session import FundHalted
from hedge_fund.pipeline.test_clock import Tape
from hedge_fund.pipeline.test_stages import FakeAnalyst

DAY, NEXT = "2024-06-04", "2024-06-05"
BARS = ["13:00:00", "13:05:00", "13:10:00"]  # a three-bar window, 13:00–13:10, every 5m


@pytest.fixture(autouse=True)
def registered_fakes(monkeypatch):
    from hedge_fund.signals import ALPHA_MODEL_REGISTRY
    monkeypatch.setitem(ALPHA_MODEL_REGISTRY, "a", FakeAnalyst)


def _spec(**overrides):
    return FundSpec(**{
        "schema_version": 2, "name": "bars",
        "strategies": [{"name": "solo", "models": [{"name": "a"}], "blend": {"mode": "long_short"}}],
        "risk": {"max_position_pct": 1, "max_gross_exposure": 1}, "capital": 100_000,
        "costs": {"spread_bps": 0, "commission_per_share": 0}, "rebalance": "minute", "interval": 5, "window": {"start": "13:00", "end": "13:10"},
        **overrides,
    })


def _at(day, hhmmss):
    return datetime.fromisoformat(f"{day}T{hhmmss}").replace(tzinfo=NEW_YORK)


def _tape(now):
    path = {"AAPL": {}, "SPY": {}}
    for i, (day, bar) in enumerate((d, b) for d in (DAY, NEXT) for b in BARS):
        path["AAPL"][f"{day}T{bar}"] = 100.0 + i
        path["SPY"][f"{day}T{bar}"] = 500.0
    return Tape(path, now=now)


class Loop:
    """Drives `run`: sleeping moves the fake clock; stops after N records,
    or when the clock passes *until* (a runaway loop in a test ends there)."""

    def __init__(self, directory, tape, *, records=1, until=None):
        self.directory, self.tape = directory, tape
        self.stop = threading.Event()
        self.records, self.events = [], []
        self._wanted = records
        self._until = until or _at(NEXT, "23:00:00")

    def __call__(self):
        run(self.directory, self.tape, stop=self.stop, build_fund=build_fund, now=lambda: self.tape.now,
            sleep=self._sleep, on_record=self._record, on_event=lambda k, f: self.events.append((k, f)))

    def _sleep(self, seconds):
        self.tape.now += timedelta(seconds=seconds)
        if self.tape.now > self._until:
            self.stop.set()

    def _record(self, record):
        self.records.append(record)
        if len(self.records) >= self._wanted:
            self.stop.set()


def test_a_day_of_bars_decides_fills_and_checkpoints(tmp_path):
    directory = deploy("bars", _spec(), ["AAPL"], root=tmp_path)
    tape = _tape(_at(DAY, "12:00:00"))
    loop = Loop(directory, tape, records=3)
    loop()
    ledger = Ledger(directory)
    assert [r.session for r in loop.records] == [f"{DAY}T{b}" for b in BARS]
    assert ledger.sessions() == [r.session for r in loop.records]
    first, second, third = loop.records
    assert first.decision is not None and first.executed is None
    assert second.executed is not None and second.executed.fills[0].price == 101.0
    assert second.executed.execution_policy == "next_bar" and second.positions == {"AAPL": 990}
    assert third.marks == {"AAPL": 102.0} and third.snapshot_times["AAPL"] == "2024-06-04T17:10:00Z"
    assert ledger.checkpoint_path(DAY).exists()
    assert [k for k, _ in loop.events] == [] and [e["kind"] for e in ledger.events()] == ["tick", "tick", "tick", "checkpoint"]
    assert ledger.replay(100_000) == ledger.replay(100_000, full=True)


def test_a_late_start_skips_to_the_current_bar_and_logs_the_gap(tmp_path):
    directory = deploy("bars", _spec(), ["AAPL"], root=tmp_path)
    tape = _tape(_at(DAY, "12:00:00"))
    Loop(directory, tape, records=3)()
    # Away for a day; back thirty seconds into tomorrow's 13:05 bar.
    tape.now = _at(NEXT, "13:05:30")
    loop = Loop(directory, tape, records=1)
    loop()
    record = loop.records[0]
    assert record.session == f"{NEXT}T13:05:00"
    assert loop.events == [("gap", {"from": f"{DAY}T13:10:00", "to": f"{NEXT}T13:05:00", "bars_skipped": 1})]
    # The pending decision from yesterday's close was refreshed at 13:00 today, then executed.
    assert record.executed.original_assessment.as_of == f"{DAY}T13:10:00"
    assert record.executed.refreshed_assessment.as_of == f"{NEXT}T13:00:00"
    assert record.executed.fills == [] and record.positions == {"AAPL": 990}  # same view, same book
    assert Ledger(directory).replay(100_000).last_session == record.session


def test_an_evening_start_does_not_mark_the_close_at_tonights_print(tmp_path):
    directory = deploy("bars", _spec(), ["AAPL"], root=tmp_path)
    tape = _tape(_at(DAY, "18:00:00"))
    loop = Loop(directory, tape, records=1)
    loop()
    assert loop.records[0].session == f"{NEXT}T13:00:00"
    assert loop.events == []  # nothing recorded before it: no gap to speak of


def test_a_day_the_benchmark_has_not_printed_is_skipped_once_and_quietly(tmp_path):
    directory = deploy("bars", _spec(), ["AAPL"], root=tmp_path)
    tape = _tape(_at(DAY, "12:00:00"))
    Loop(directory, tape, records=3)()
    del tape.path["SPY"][f"{NEXT}T13:00:00"], tape.path["SPY"][f"{NEXT}T13:05:00"]
    tape.now = _at(NEXT, "13:00:00")
    loop = Loop(directory, tape, records=1)
    loop()
    assert loop.records[0].session == f"{NEXT}T13:10:00"  # SPY printed again by then
    kinds = [k for k, _ in loop.events]
    assert kinds == ["gap", "gap"]
    assert "market closed" in loop.events[0][1]["reason"] and loop.events[1][1]["bars_skipped"] == 2


def test_a_failed_bar_halts_the_fund_like_a_failed_tick(tmp_path):
    directory = deploy("bars", _spec(), ["AAPL"], root=tmp_path)
    tape = _tape(_at(DAY, "12:00:00"))
    Loop(directory, tape, records=1)()
    del tape.path["AAPL"]  # the next bar cannot be valued: no AAPL prints at all
    tape.path["AAPL"] = {}
    loop = Loop(directory, tape, records=1)
    with pytest.raises(ValueError):
        loop()
    ledger = Ledger(directory)
    assert ledger.halted().startswith(f"tick {DAY}T13:05:00 failed")
    with pytest.raises(FundHalted):
        Loop(directory, tape, records=1)()


def test_redo_runs_a_bar_again_at_the_prices_it_saw(tmp_path):
    directory = deploy("bars", _spec(), ["AAPL"], root=tmp_path)
    tape = _tape(_at(DAY, "12:00:00"))
    loop = Loop(directory, tape, records=3)
    loop()
    tape.snapshot_calls.clear()
    again = redo(directory, tape, build_fund=build_fund)
    assert tape.snapshot_calls == []  # no new prints were taken
    assert again.session == loop.records[2].session and again.marks == loop.records[2].marks
    assert again.hash == loop.records[2].hash  # same prints, same analysts: the same record
    ledger = Ledger(directory)
    assert ledger.replay(100_000).last_session == again.session
    assert [e["kind"] for e in ledger.events()][-3:] == ["redo", "tick", "checkpoint"]
    assert ledger.checkpoint_path(DAY).exists()  # the closing bar, run again, closes the day again
    assert ledger.replay(100_000) == ledger.replay(100_000, full=True)

    def bearish(spec):
        return Fund(spec, models={"solo": [FakeAnalyst("a", {"AAPL": -1})]})
    flipped = redo(directory, tape, build_fund=bearish)
    assert flipped.decision.final_weights == {"AAPL": -1.0} and flipped.hash != again.hash


def test_tick_runs_the_current_bar_by_hand_at_the_print_taken_now(tmp_path):
    """Enter on a minute fund is the same verb as on a daily one: the next
    session, which is the latest bar boundary passed. Pressed late, the bar
    is recorded at the print taken now, and the record says when that was.
    A holiday is nothing due; the closing bar checkpoints the day."""
    directory = deploy("bars", _spec(), ["AAPL"], root=tmp_path)
    tape = _tape(_at(DAY, "12:00:00"))
    with pytest.raises(NothingDue, match="no bar yet; next 13:00:00 ET"):
        tick(directory, tape, build_fund=build_fund, now=lambda: tape.now)

    tape.now = _at(DAY, "13:00:00")
    first = tick(directory, tape, build_fund=build_fund, now=lambda: tape.now)
    assert first.session == f"{DAY}T13:00:00" and first.decision is not None
    with pytest.raises(NothingDue, match=f"no bar after {DAY}T13:00:00; next 13:05:00 ET"):
        tick(directory, tape, build_fund=build_fund, now=lambda: tape.now)

    tape.now = _at(DAY, "13:07:30")  # two and a half minutes into the 13:05 bar
    second = tick(directory, tape, build_fund=build_fund, now=lambda: tape.now)
    assert second.session == f"{DAY}T13:05:00" and second.executed.fills[0].price == 101.0
    assert second.snapshot_times["AAPL"] == "2024-06-04T17:05:00Z"  # the latest print on the tape, as taken

    tape.now = _at(DAY, "13:10:00")
    third = tick(directory, tape, build_fund=build_fund, now=lambda: tape.now)
    ledger = Ledger(directory)
    assert third.session == f"{DAY}T13:10:00" and ledger.checkpoint_path(DAY).exists()
    assert [e["kind"] for e in ledger.events()] == ["tick", "tick", "tick", "checkpoint"]

    del tape.path["SPY"][f"{NEXT}T13:00:00"]  # the market has not opened tomorrow by the first bar
    tape.now = _at(NEXT, "13:00:00")
    with pytest.raises(NothingDue, match="SPY has not printed today"):
        tick(directory, tape, build_fund=build_fund, now=lambda: tape.now)
    assert ledger.sessions()[-1] == third.session


class DailyTape(FakeDataClient):
    """Daily closes, and a clock the test moves."""

    def __init__(self, series, *, now):
        super().__init__(series)
        self.now = now


def test_a_daily_fund_is_run_unattended_too_catching_up_after_each_midnight(tmp_path):
    """The same loop at the daily cadence: every session that has become
    due since it last looked, oldest first, then sleep to the turn of the
    day. A fresh fund starts at the latest completed close, as a tick would."""
    spec = FundSpec(**{**_spec().model_dump(exclude={"interval", "window"}), "rebalance": "daily"})
    directory = deploy("daily", spec, ["AAPL"], root=tmp_path)
    tape = DailyTape(SERIES, now=_at("2024-06-04", "12:00:00"))
    loop = Loop(directory, tape, records=1)
    loop()
    assert [r.session for r in loop.records] == ["2024-06-03"]  # Tuesday noon: Monday is the latest close

    tape.now = _at("2024-06-06", "23:30:00")  # away two days; two closes have become due
    loop = Loop(directory, tape, records=2)
    loop()
    assert [r.session for r in loop.records] == ["2024-06-04", "2024-06-05"]
    assert loop.records[0].executed is not None and loop.records[0].positions == {"AAPL": 500}
    assert tape.now == _at("2024-06-06", "23:30:00")  # caught up without sleeping between them

    loop = Loop(directory, tape, records=1, until=_at("2024-06-08", "00:00:00"))
    loop()
    assert loop.records[0].session == "2024-06-06"  # nothing was due at 23:30; it slept to the turn of the day
    assert tape.now == _at("2024-06-07", "00:05:00")
    assert loop.events == [] and Ledger(directory).sessions() == ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"]


def test_serve_holds_a_pid_file_and_stops_on_sigterm(tmp_path, monkeypatch):
    directory = deploy("bars", _spec(), ["AAPL"], root=tmp_path)
    assert not is_running(directory) and not stop_runner(directory)
    (directory / PID_FILE).write_text("999999999")
    assert not is_running(directory)  # a stale pid is not a runner

    import hedge_fund.paper.runner as runner
    seen = {}

    def quick(directory, data, *, stop, **kwargs):
        seen["pid"] = int((directory / PID_FILE).read_text())
        seen["running"] = is_running(directory)
        threading.Timer(0.05, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
        seen["stopped"] = stop.wait(5)
    monkeypatch.setattr(runner, "run", quick)

    serve(directory, _tape(_at(DAY, "12:59:00")))
    assert seen == {"pid": os.getpid(), "running": True, "stopped": True}
    assert not (directory / PID_FILE).exists() and not is_running(directory)
    # Two runners on one fund is a race on the ledger: the second refuses.
    (directory / PID_FILE).write_text(str(os.getpid()))
    with pytest.raises(RuntimeError, match="already running"):
        serve(directory, _tape(_at(DAY, "12:59:00")))
