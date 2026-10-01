"""tick — deploy, advance one session at a time, and halt on failure."""

import json
from datetime import datetime

import pytest
import yaml

from hedge_fund.backtesting.fund import backtest_fund
from hedge_fund.backtesting.test_fund import FakeAnalyst, FakeDataClient, SERIES, WEEKDAYS
from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.data import sessions
from hedge_fund.fund import Fund, FundSpec
from hedge_fund.paper import (
    deploy,
    Ledger,
    list_deployed,
    load_deployed,
    next_session,
    NothingDue,
    redo,
    tick,
    validate_fund_name,
)
from hedge_fund.pipeline.session import FundHalted


@pytest.fixture(autouse=True)
def registered_fakes(monkeypatch):
    from hedge_fund.signals import ALPHA_MODEL_REGISTRY
    monkeypatch.setitem(ALPHA_MODEL_REGISTRY, "a", FakeAnalyst)


@pytest.fixture
def clock(monkeypatch):
    """Pin 'now' so completed_through() is deterministic; returns a setter."""
    def set_today(day: str, hour: int = 12):
        y, m, d = map(int, day.split("-"))
        class Clock:
            @staticmethod
            def now(tz):
                return datetime(y, m, d, hour, tzinfo=tz)
        monkeypatch.setattr(sessions, "datetime", Clock)
    return set_today


@pytest.fixture
def SPEC(registered_fakes):
    return FundSpec(schema_version=2, name="paper-fund",
                    strategies=[{"name": "solo", "models": [{"name": "a"}], "blend": {"mode": "long_short"}}],
                    risk={"max_position_pct": 1, "max_gross_exposure": 1}, capital=100_000)


def build_fund(spec):
    return Fund(spec, models={"solo": [FakeAnalyst("a", {"AAPL": 1})]})


def _tick(directory, session=None, data=None):
    return tick(directory, data or FakeDataClient(SERIES), session=session, build_fund=build_fund)


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------

def test_deploy_lays_out_the_fund_directory(tmp_path, SPEC):
    directory = deploy("alpha", SPEC, ["aapl", "AAPL", "msft"], root=tmp_path)
    assert directory == tmp_path / "alpha"
    deployed = load_deployed(directory)
    assert deployed.name == "alpha" and deployed.spec == SPEC
    assert deployed.universe == ["AAPL", "MSFT"] and deployed.broker == "paper"
    assert yaml.safe_load((directory / "fund.yaml").read_text())["spec"]["name"] == "paper-fund"
    assert json.loads((directory / "broker.json").read_text()) == {"cash": 100_000, "shares": {}}
    assert json.loads((directory / "control.json").read_text()) == {"halted": False}
    assert (directory / "ledger").is_dir() and Ledger(directory).sessions() == []
    assert list_deployed(tmp_path) == [directory]
    assert list_deployed(tmp_path / "nowhere") == []
    with pytest.raises(FileExistsError, match="already exists"):
        deploy("alpha", SPEC, ["AAPL"], root=tmp_path)


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "-lead", ".hidden", "sp ace"])
def test_deploy_rejects_unsafe_names(tmp_path, bad, SPEC):
    with pytest.raises(ValueError, match="invalid fund name"):
        validate_fund_name(bad)
    with pytest.raises(ValueError):
        deploy(bad, SPEC, ["AAPL"], root=tmp_path)
    assert list_deployed(tmp_path) == []


def test_load_deployed_reports_the_path_on_bad_files(tmp_path, SPEC):
    (tmp_path / "fund.yaml").write_text("[oops")
    with pytest.raises(ValueError, match="fund.yaml"):
        load_deployed(tmp_path)
    (tmp_path / "fund.yaml").write_text("name: x\n")
    with pytest.raises(ValueError, match="spec"):
        load_deployed(tmp_path)


# ---------------------------------------------------------------------------
# next_session
# ---------------------------------------------------------------------------

def test_next_session_is_latest_completed_for_a_fresh_fund_and_the_next_one_after(clock):
    clock("2024-06-13")  # completed through 06-12
    data = FakeDataClient(SERIES)
    assert next_session(data, "SPY", None) == "2024-06-12"
    assert next_session(data, "SPY", "2024-06-07") == "2024-06-10"
    assert next_session(data, "SPY", "2024-06-12") is None
    clock("2024-06-03")  # nothing completed inside the series yet
    assert next_session(data, "SPY", None) is None


# ---------------------------------------------------------------------------
# tick
# ---------------------------------------------------------------------------

def test_ticks_advance_one_session_each_and_match_the_backtest(tmp_path, clock, SPEC):
    clock("2024-06-04")  # the fund is deployed Tuesday morning: Monday is the latest close
    directory = deploy("alpha", SPEC, ["AAPL"], root=tmp_path)

    monday = _tick(directory)
    assert monday.session == "2024-06-03" and monday.rebalance
    assert monday.decision is not None and monday.executed is None
    with pytest.raises(NothingDue, match="after 2024-06-03"):
        _tick(directory)

    clock("2024-06-06")  # two closes have gone by; ticks catch up one at a time
    tuesday = _tick(directory)
    assert tuesday.session == "2024-06-04"
    assert tuesday.executed.execution_as_of == "2024-06-04"
    assert tuesday.positions == {"AAPL": 500}
    assert json.loads((directory / "broker.json").read_text()) == {"cash": 0, "shares": {"AAPL": 500}}
    wednesday = _tick(directory)
    assert wednesday.session == "2024-06-05" and wednesday.executed is None

    assert Ledger(directory).sessions() == WEEKDAYS[:3]
    replayed = backtest_fund(build_fund(SPEC), WEEKDAYS[0], WEEKDAYS[2], FakeDataClient(SERIES), ["AAPL"])
    assert Ledger(directory).records() == replayed.records
    kinds = [e["kind"] for e in Ledger(directory).events()]
    assert kinds == ["tick", "tick", "tick"]


def test_explicit_session_is_idempotent_and_must_be_the_next_one(tmp_path, clock, SPEC):
    clock("2024-06-06")
    directory = deploy("alpha", SPEC, ["AAPL"], root=tmp_path)
    first = _tick(directory)  # fresh fund: latest completed close, 06-05
    assert first.session == "2024-06-05"
    assert _tick(directory, session="2024-06-05") == first  # no-op, nothing appended
    assert Ledger(directory).sessions() == ["2024-06-05"]
    clock("2024-06-11")
    with pytest.raises(ValueError, match="not the next unrecorded session \\(2024-06-06\\)"):
        _tick(directory, session="2024-06-10")
    assert _tick(directory, session="2024-06-06").session == "2024-06-06"


def test_redo_runs_the_latest_session_again_and_replaces_its_record(tmp_path, clock, SPEC):
    spec = SPEC.model_copy(update={"rebalance": "daily"})
    clock("2024-06-04")
    directory = deploy("alpha", spec, ["AAPL"], root=tmp_path)
    ledger = Ledger(directory)
    with pytest.raises(NothingDue, match="nothing to run again"):
        redo(directory, FakeDataClient(SERIES), build_fund=build_fund)
    _tick(directory)                         # 06-03: decided, long AAPL
    clock("2024-06-05")
    tuesday = _tick(directory)               # 06-04: bought 500 AAPL, decided again
    assert tuesday.positions == {"AAPL": 500} and tuesday.decision.final_weights == {"AAPL": 1.0}
    book_before = json.loads((directory / "broker.json").read_text())

    # Same analysts, same close: the redo reproduces the session exactly. The
    # point is the book — without the restore, the broker would still hold
    # Tuesday's 500 shares going in and the reconciliation would halt the fund.
    same = redo(directory, FakeDataClient(SERIES), build_fund=build_fund)
    assert same == tuesday
    assert json.loads((directory / "broker.json").read_text()) == book_before
    kept = sorted((directory / "ledger" / "superseded").glob("*.json"))
    assert [p.name for p in kept] == [f"2024-06-04.{tuesday.hash[:12]}.json"]
    assert json.loads(kept[0].read_text())["hash"] == tuesday.hash

    # The analysts changed their minds by the evening: the 06-03 decision is
    # still what gets executed, but the new decision is different.
    bearish = redo(directory, FakeDataClient(SERIES),
                   build_fund=lambda s: Fund(s, models={"solo": [FakeAnalyst("a", {"AAPL": -1})]}))
    assert bearish.session == "2024-06-04" and bearish.prev_hash == tuesday.prev_hash
    assert bearish.positions == {"AAPL": 500}                    # executed the same pending decision
    assert bearish.decision.final_weights == {"AAPL": -1.0}      # but decided differently
    assert bearish.hash != tuesday.hash
    assert ledger.sessions() == ["2024-06-03", "2024-06-04"] and ledger.latest() == bearish
    assert ledger.replay(spec.capital).pending == bearish.decision  # the chain still verifies
    assert [e["kind"] for e in ledger.events()] == ["tick", "tick", "redo", "tick", "redo", "tick"]

    # The next real tick still finds 06-05 due and executes the redone decision.
    clock("2024-06-06")
    wednesday = _tick(directory)
    assert wednesday.session == "2024-06-05" and wednesday.executed.as_of == "2024-06-04"
    assert wednesday.positions == {"AAPL": -500}


def test_redo_refuses_a_halted_fund_and_leaves_it_untouched(tmp_path, clock, SPEC):
    clock("2024-06-04")
    directory = deploy("alpha", SPEC, ["AAPL"], root=tmp_path)
    first = _tick(directory)
    Ledger(directory).halt("looking into it")
    with pytest.raises(FundHalted):
        redo(directory, FakeDataClient(SERIES), build_fund=build_fund)
    assert Ledger(directory).latest() == first
    assert not (directory / "ledger" / "superseded").exists()


def test_failure_inside_advance_halts_the_fund_and_a_resume_clears_it(tmp_path, clock, SPEC):
    clock("2024-06-05")
    directory = deploy("alpha", SPEC, ["AAPL"], root=tmp_path)
    _tick(directory)  # 06-04, decision made
    clock("2024-06-06")
    series = {t: dict(v) for t, v in SERIES.items()}
    del series["AAPL"]["2024-06-05"]  # execution price missing at the next close
    with pytest.raises(ValueError, match="AAPL: missing close on 2024-06-05"):
        _tick(directory, data=FakeDataClient(series))
    ledger = Ledger(directory)
    assert ledger.halted().startswith("tick 2024-06-05 failed: ValueError")
    assert [e["kind"] for e in ledger.events()] == ["tick", "tick_failed", "halt"]
    assert ledger.sessions() == ["2024-06-04"]
    with pytest.raises(FundHalted):
        _tick(directory)  # data is fine again, but nobody has looked yet
    ledger.resume()
    assert _tick(directory).session == "2024-06-05"


def test_broker_drift_between_ticks_is_caught_and_halts(tmp_path, clock, SPEC):
    clock("2024-06-05")
    directory = deploy("alpha", SPEC, ["AAPL"], root=tmp_path)
    _tick(directory)
    book = json.loads((directory / "broker.json").read_text())
    book["cash"] -= 5
    (directory / "broker.json").write_text(json.dumps(book))
    clock("2024-06-06")
    from hedge_fund.pipeline.session import BookMismatch
    with pytest.raises(BookMismatch, match="cash"):
        _tick(directory)
    assert "BookMismatch" in Ledger(directory).halted()
    assert PaperBroker(directory / "broker.json").positions() == {}  # nothing traded
