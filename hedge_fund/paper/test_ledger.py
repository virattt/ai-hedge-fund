"""The ledger: append-only, hash-chained, replayable; and the kill switch."""

import json

import pytest

from hedge_fund.backtesting.fund import backtest_fund
from hedge_fund.backtesting.test_fund import FakeAnalyst, FakeDataClient, SERIES, WEEKDAYS
from hedge_fund.fund import Fund, FundSpec
from hedge_fund.paper.ledger import Ledger, LedgerError
from hedge_fund.pipeline.session import FundState, SessionRecord


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


def _bar(session, prev=None, nav=100_000.0):
    """A hand-made bar record chained to *prev*."""
    record = SessionRecord(
        fund="bars", session=session, universe=["AAPL"], nav=nav, cash=nav, positions={},
        marks={}, benchmark="SPY", benchmark_close=500.0, rebalance=True,
        prev_hash=prev.hash if prev else None, code_version="test", mandate_hash="m",
        snapshot_times={"SPY": "2026-10-05T14:00:00Z"},
    )
    record.hash = record.compute_hash()
    return record


def _chain(sessions):
    records, prev = [], None
    for i, session in enumerate(sessions):
        prev = _bar(session, prev, nav=100_000.0 + i)
        records.append(prev)
    return records


MONDAY = ["2026-10-05T09:30:00", "2026-10-05T09:35:00", "2026-10-05T16:00:00"]
TUESDAY = ["2026-10-06T09:30:00", "2026-10-06T16:00:00"]


def test_bars_live_in_a_directory_per_day_and_list_in_chain_order(tmp_path):
    ledger = Ledger(tmp_path)
    for record in _chain(MONDAY + TUESDAY):
        ledger.append(record)
    assert ledger.path(MONDAY[1]) == tmp_path / "ledger" / "2026-10-05" / "093500.json"
    assert ledger.sessions() == MONDAY + TUESDAY
    assert ledger.days() == ["2026-10-05", "2026-10-06"]
    assert ledger.read(MONDAY[1]).session == MONDAY[1]
    assert [r.session for r in ledger.records(since="2026-10-06")] == TUESDAY
    assert ledger.replay(100_000).last_session == TUESDAY[-1]
    # A daily record and bar records can share a ledger's listing rules.
    assert ledger.sessions() == sorted(ledger.sessions())


def test_checkpoint_shortcuts_replay_and_is_ignored_once_the_chain_moves_under_it(tmp_path):
    ledger = Ledger(tmp_path)
    records = _chain(MONDAY + TUESDAY)
    for record in records[:3]:
        ledger.append(record)
    with pytest.raises(LedgerError, match="only a minute fund"):
        ledger.checkpoint(FundState.initial(1.0))
    with pytest.raises(LedgerError, match="does not match the chain's head"):
        ledger.checkpoint(ledger.replay(100_000, before=MONDAY[2]))
    monday_close = ledger.replay(100_000)
    path = ledger.checkpoint(monday_close)
    assert path == tmp_path / "ledger" / "2026-10-05" / "checkpoint.json"
    assert [e["kind"] for e in ledger.events()] == ["checkpoint"]
    for record in records[3:]:
        ledger.append(record)
    # From the checkpoint only Tuesday is read; the answer is the full walk's.
    read = []
    original = ledger.read
    ledger.read = lambda s: (read.append(s), original(s))[1]
    short = ledger.replay(100_000)
    assert read == [MONDAY[2], *TUESDAY] and short == ledger.replay(100_000, full=True)
    read.clear()
    assert ledger.replay(100_000, before=TUESDAY[1]).last_session == TUESDAY[0] and read == [MONDAY[2], TUESDAY[0]]
    read.clear()
    assert ledger.replay(100_000, before=MONDAY[1]).last_session == MONDAY[0] and read == [MONDAY[0]]
    # Rewinding past the checkpoint drops it; a stale one on disk is ignored.
    ledger.rewind(); ledger.rewind()
    assert (tmp_path / "ledger" / "superseded" / f"2026-10-06T093000.{records[3].hash[:12]}.json").exists()
    ledger.rewind()
    assert not path.exists() and ledger.replay(100_000).last_session == MONDAY[1]
    path.write_text(monday_close.model_dump_json())
    assert ledger.replay(100_000).last_session == MONDAY[1]


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
