"""advance — the guards, the reconciliation, and the T / T+1 sequencing."""

from unittest.mock import Mock

import pytest

from hedge_fund.backtesting.fund import backtest_fund
from hedge_fund.backtesting.test_fund import FakeAnalyst, FakeDataClient, SERIES, WEEKDAYS
from hedge_fund.brokers.models import Order
from hedge_fund.brokers.sim import SimBroker
from hedge_fund.fund import Fund, FundSpec
from hedge_fund.pipeline.session import (
    advance,
    BookMismatch,
    FundHalted,
    FundState,
    is_rebalance_session,
    next_state,
    SessionRecord,
)


def _fund(**overrides):
    base = dict(
        schema_version=2, name="session-fund",
        strategies=[{"name": "solo", "models": [{"name": "a"}], "blend": {"mode": "long_short"}}],
        risk={"max_position_pct": 1.0, "max_gross_exposure": 1.0},
        capital=100_000.0, rebalance="weekly",
    )
    spec = FundSpec(**{**base, **overrides})
    return Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})


@pytest.fixture(autouse=True)
def registered_fakes(monkeypatch):
    from hedge_fund.signals import ALPHA_MODEL_REGISTRY
    monkeypatch.setitem(ALPHA_MODEL_REGISTRY, "a", FakeAnalyst)


def _step(fund, sessions, broker=None, state=None, data=None):
    broker = broker or SimBroker(cash=fund.spec.capital)
    state = state or FundState.initial(fund.spec.capital)
    data = data or FakeDataClient(SERIES)
    records = []
    for session in sessions:
        records.append(advance(fund, state, session, broker, data, ["AAPL"]))
        state = next_state(state, records[-1])
    return records, state


# ---------------------------------------------------------------------------
# The rebalance rule
# ---------------------------------------------------------------------------

def test_first_session_of_period_rule_looks_back_only():
    assert is_rebalance_session("2024-06-05", None, "weekly")          # a fund's first session
    assert is_rebalance_session("2024-06-05", None, "monthly")
    assert is_rebalance_session("2024-06-05", "2024-06-04", "daily")
    assert not is_rebalance_session("2024-06-05", "2024-06-04", "weekly")  # same ISO week
    assert is_rebalance_session("2024-06-10", "2024-06-07", "weekly")      # Monday after Friday
    assert is_rebalance_session("2024-06-11", "2024-06-07", "weekly")      # Monday was a holiday
    assert not is_rebalance_session("2024-06-28", "2024-06-27", "monthly")
    assert is_rebalance_session("2024-07-01", "2024-06-28", "monthly")
    # Dec 30 2024 – Jan 2 2025: one ISO week, two calendar months.
    assert not is_rebalance_session("2025-01-02", "2024-12-31", "weekly")
    assert is_rebalance_session("2025-01-02", "2024-12-31", "monthly")
    with pytest.raises(ValueError, match="cadence"):
        is_rebalance_session("2024-06-05", None, "hourly")


# ---------------------------------------------------------------------------
# Sequencing: decide at T, execute at T+1
# ---------------------------------------------------------------------------

def test_decision_at_t_executes_at_t_plus_one_across_two_advances():
    fund = _fund()
    (monday, tuesday), state = _step(fund, WEEKDAYS[:2])

    assert monday.rebalance and monday.decision is not None and monday.executed is None
    assert monday.positions == {} and monday.nav == 100_000 and monday.cash == 100_000
    assert monday.decision.final_weights == {"AAPL": 1.0}

    assert not tuesday.rebalance and tuesday.decision is None
    assert tuesday.executed.as_of == monday.session
    assert tuesday.executed.execution_as_of == tuesday.session
    assert tuesday.positions == {"AAPL": 500} and tuesday.cash == 0 and tuesday.nav == 100_000
    assert tuesday.marks == {"AAPL": 200.0} and tuesday.benchmark_close == 100.0

    assert state.last_session == tuesday.session
    assert state.pending is None and state.positions == {"AAPL": 500}
    assert state.prev_hash == tuesday.hash


def test_next_state_carries_the_decision_and_the_chain():
    fund = _fund()
    (monday,), state = _step(fund, WEEKDAYS[:1])
    assert state == FundState(positions={}, cash=100_000, last_session=monday.session,
                              pending=monday.decision, prev_hash=monday.hash)
    assert monday.prev_hash is None
    assert monday.hash == monday.compute_hash()
    assert SessionRecord.model_validate_json(monday.model_dump_json()) == monday


def test_step_by_step_advance_matches_the_backtest_exactly():
    """Paper trading is the backtest one tick at a time: same records, same hashes."""
    stepped, _ = _step(_fund(), WEEKDAYS)
    replayed = backtest_fund(_fund(), WEEKDAYS[0], WEEKDAYS[-1], FakeDataClient(SERIES), ["AAPL"])
    assert stepped == replayed.records


def test_record_stamps_code_and_mandate_versions():
    fund = _fund()
    (record,), _ = _step(fund, WEEKDAYS[:1])
    assert record.code_version
    assert len(record.mandate_hash) == 64
    assert record.llm_model is None  # no LLM agents on this desk


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def test_out_of_order_and_repeated_sessions_are_refused():
    fund = _fund()
    _, state = _step(fund, WEEKDAYS[:2])
    broker = Mock()  # the guard fires before reconciliation ever looks at the broker
    for session in (WEEKDAYS[1], WEEKDAYS[0]):
        with pytest.raises(ValueError, match="not after the last recorded session"):
            advance(fund, state, session, broker, FakeDataClient(SERIES), ["AAPL"])
    assert broker.method_calls == []


def test_halted_fund_refuses_before_touching_broker_or_data():
    fund = _fund()
    broker = Mock()
    data = Mock()
    state = FundState.initial(100_000).model_copy(update={"halted": "operator said stop"})
    with pytest.raises(FundHalted, match="operator said stop"):
        advance(fund, state, WEEKDAYS[0], broker, data, ["AAPL"])
    assert broker.method_calls == [] and data.method_calls == []


def test_book_mismatch_raises_before_any_order_or_analyst_call():
    fund = _fund()
    analyst = fund.strategies[0][1][0]
    analyst.predict = Mock(side_effect=AssertionError("analyst called"))
    broker = SimBroker(cash=100_000)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=1, price=200))  # broker drifted
    broker.place_order = Mock(side_effect=AssertionError("order placed"))
    with pytest.raises(BookMismatch, match=r"AAPL: broker \+1 vs ledger \+0"):
        advance(fund, FundState.initial(100_000), WEEKDAYS[0], broker, FakeDataClient(SERIES), ["AAPL"])
    cash_only = SimBroker(cash=99_000)
    with pytest.raises(BookMismatch, match="cash: broker 99,000.00 vs ledger 100,000.00"):
        advance(fund, FundState.initial(100_000), WEEKDAYS[0], cash_only, FakeDataClient(SERIES), ["AAPL"])
    analyst.predict.assert_not_called()


def test_a_book_that_agrees_reconciles_even_with_positions():
    fund = _fund()
    broker = SimBroker(cash=0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=500, price=200))
    broker._cash = 0.0  # 100k spent at 200 leaves exactly zero
    state = FundState(positions={"AAPL": 500}, cash=0.0, last_session=WEEKDAYS[0])
    record = advance(fund, state, WEEKDAYS[1], broker, FakeDataClient(SERIES), ["AAPL"])
    assert record.positions == {"AAPL": 500} and record.nav == 100_000


def test_analyst_failure_propagates_and_places_no_orders():
    fund = _fund()
    fund.strategies[0][1][0].predict = Mock(side_effect=ConnectionError("API down"))
    broker = SimBroker(cash=100_000)
    with pytest.raises(ConnectionError):
        advance(fund, FundState.initial(100_000), WEEKDAYS[0], broker, FakeDataClient(SERIES), ["AAPL"])
    assert broker.positions() == {} and broker.cash() == 100_000
