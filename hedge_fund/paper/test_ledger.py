"""The ledger: append-only, hash-chained, replayable; and the kill switch."""

import json

import pytest

from hedge_fund.backtesting.fund import backtest_fund
from hedge_fund.backtesting.test_fund import FakeAnalyst, FakeDataClient, SERIES, WEEKDAYS
from hedge_fund.fund import Fund, FundSpec
from hedge_fund.paper.ledger import Ledger, LedgerError
from hedge_fund.pipeline.session import FundState


@pytest.fixture(autouse=True)
def registered_fakes(monkeypatch):
    from hedge_fund.signals import ALPHA_MODEL_REGISTRY
    monkeypatch.setitem(ALPHA_MODEL_REGISTRY, "a", FakeAnalyst)


@pytest.fixture
def records():
    spec = FundSpec(schema_version=2, name="ledger-fund",
                    strategies=[{"name": "solo", "models": [{"name": "a"}], "blend": {"mode": "long_short"}}],
                    risk={"max_position_pct": 1, "max_gross_exposure": 1}, capital=100_000)
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", {"AAPL": 1})]})
    return backtest_fund(fund, WEEKDAYS[0], WEEKDAYS[4], FakeDataClient(SERIES), ["AAPL"]).records


def test_append_then_replay_rebuilds_the_state(tmp_path, records):
    ledger = Ledger(tmp_path)
    ledger.init()
    assert ledger.sessions() == [] and ledger.latest() is None
    assert ledger.replay(100_000) == FundState.initial(100_000)

    for record in records:
        path = ledger.append(record)
        assert path == tmp_path / "ledger" / f"{record.session}.json"
    assert ledger.sessions() == WEEKDAYS[:5]
    assert ledger.latest() == records[-1]
    assert ledger.read(WEEKDAYS[1]) == records[1]
    assert ledger.records() == records

    state = ledger.replay(100_000)
    assert state.positions == {"AAPL": 500} and state.cash == 0
    assert state.last_session == WEEKDAYS[4]
    assert state.pending is None  # Friday is not a rebalance session
    assert state.prev_hash == records[-1].hash
    assert state.halted is None


def test_append_refuses_duplicates_gaps_and_bad_hashes(tmp_path, records):
    ledger = Ledger(tmp_path)
    ledger.append(records[0])
    with pytest.raises(LedgerError, match="already recorded"):
        ledger.append(records[0])
    with pytest.raises(LedgerError, match="does not chain"):
        ledger.append(records[2])  # skipped records[1]
    tampered = records[1].model_copy(update={"nav": 1.0})
    with pytest.raises(LedgerError, match="hash does not match"):
        ledger.append(tampered)
    ledger.append(records[1])
    backdated = records[2].model_copy(update={"session": "2024-05-31"})
    backdated.hash = backdated.compute_hash()
    with pytest.raises(LedgerError, match="not after"):
        ledger.append(backdated)
    assert ledger.sessions() == WEEKDAYS[:2]


def test_replay_detects_an_edited_record(tmp_path, records):
    ledger = Ledger(tmp_path)
    for record in records[:3]:
        ledger.append(record)
    path = ledger.path(WEEKDAYS[1])
    data = json.loads(path.read_text())
    data["cash"] = 999.0
    path.write_text(json.dumps(data))
    with pytest.raises(LedgerError, match="altered"):
        ledger.replay(100_000)


def test_replay_detects_a_missing_link(tmp_path, records):
    ledger = Ledger(tmp_path)
    for record in records[:3]:
        ledger.append(record)
    ledger.path(WEEKDAYS[1]).unlink()
    with pytest.raises(LedgerError, match="chain broken at session 2024-06-05"):
        ledger.replay(100_000)


def test_kill_switch_round_trips_and_logs(tmp_path):
    ledger = Ledger(tmp_path)
    ledger.init()
    assert ledger.halted() is None
    assert json.loads(ledger.control_path.read_text()) == {"halted": False}
    ledger.halt("drawdown breach")
    assert ledger.halted() == "drawdown breach"
    assert ledger.replay(1.0).halted == "drawdown breach"
    ledger.resume()
    assert ledger.halted() is None
    assert [e["kind"] for e in ledger.events()] == ["halt", "resume"]
    assert ledger.events()[0]["reason"] == "drawdown breach"
    assert all("time" in e for e in ledger.events())
