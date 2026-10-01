"""Assessment cutoffs and exact-session execution with controlled market data."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from hedge_fund.backtesting.test_fund import FakeDataClient
from hedge_fund.brokers.models import Order
from hedge_fund.brokers.sim import SimBroker
from hedge_fund.data import sessions
from hedge_fund.fund import Fund, FundSpec
from hedge_fund.models import Signal
from hedge_fund.pipeline.models import CycleRecord, DecisionRecord
from hedge_fund.pipeline.session import advance, FundState, next_state
from hedge_fund.pipeline.stages import assess_fund, execute_decision

FRIDAY = "2024-06-07"
MONDAY = "2024-06-10"


class DatedAnalyst:
    def __init__(self, views=None):
        self.views = views or {FRIDAY: 1, "2024-06-09": -1}
        self.calls = []

    def predict(self, ticker, date, data_client):
        self.calls.append((ticker, date))
        # A model can request the complete daily history up to its cutoff.
        assert all(bar.time[:10] <= date for bar in data_client.get_prices(ticker, FRIDAY, date))
        return Signal(model_name="druckenmiller", ticker=ticker, date=date,
                      value=self.views.get(date, 1))


def make_fund(analyst=None):
    analyst = analyst or DatedAnalyst()
    spec = FundSpec(schema_version=2, name="timing", capital=10_000,
                    strategies=[{"name": "macro", "models": [{"name": "druckenmiller"}],
                                 "blend": {"mode": "long_short"}}],
                    risk={"max_position_pct": 1, "max_gross_exposure": 1})
    return Fund(spec, models={"macro": [analyst]}), analyst


def market(execution=MONDAY, price=200):
    return FakeDataClient({"SPY": {FRIDAY: 100, execution: 101},
                           "A": {FRIDAY: 100, execution: price}})


def _advance_through(fund, broker, data, days, state=None):
    """Advance session by session, the way a paper fund ticks; return the records."""
    state = state or FundState.initial(broker.cash())
    records = []
    for day in days:
        records.append(advance(fund, state, day, broker, data, ["A"]))
        state = next_state(state, records[-1])
    return records


def test_weekend_refresh_replaces_targets_and_uses_execution_prices():
    fund, analyst = make_fund()
    broker = SimBroker(10_000)
    friday, monday = _advance_through(fund, broker, market(), [FRIDAY, MONDAY])
    # Friday decides; Monday refreshes at Sunday's cutoff, executes, then decides anew.
    assert analyst.calls == [("A", FRIDAY), ("A", "2024-06-09"), ("A", MONDAY)]
    assert friday.executed is None and friday.decision.as_of == FRIDAY
    result = monday.executed
    assert result.as_of == FRIDAY
    assert result.execution_as_of == MONDAY
    assert result.execution_policy == "next_close"
    assert result.original_assessment.final_weights == {"A": 1}
    assert result.original_assessment.marks == {"A": 100}
    assert result.refreshed_assessment.final_weights == {"A": -1}
    assert result.strategies == result.refreshed_assessment.strategies
    assert result.marks == {"A": 200}
    assert result.positions == {"A": -50}
    assert result.fills[0].price == 200
    assert monday.positions == {"A": -50} and monday.nav == 10_000
    assert CycleRecord.model_validate_json(result.model_dump_json()) == result


def test_holiday_uses_next_observed_session_and_preceding_day():
    fund, analyst = make_fund()
    _, tuesday = _advance_through(fund, SimBroker(10_000), market("2024-06-11"), [FRIDAY, "2024-06-11"])
    assert tuesday.executed.execution_as_of == "2024-06-11"
    assert analyst.calls[1] == ("A", "2024-06-10")  # the refresh, at the day before execution


def test_same_cutoff_reuses_assessment_and_records_are_snapshots():
    fund, analyst = make_fund()
    proposal = assess_fund(fund, "2024-06-09", market(), ["A"])
    result = execute_decision(fund, proposal, MONDAY, SimBroker(10_000), market())
    assert analyst.calls == [("A", "2024-06-09")]
    assert result.original_assessment == result.refreshed_assessment
    fund.spec.name = "changed"
    assert result.spec.name == result.original_assessment.spec.name == "timing"


def test_execution_revalues_existing_positions_before_sizing():
    fund, _ = make_fund()
    broker = SimBroker(10_000)
    broker.place_order(Order(ticker="A", side="buy", quantity=50, price=100))
    carried = FundState(positions={"A": 50}, cash=5_000)  # what the ledger would say
    _, monday = _advance_through(fund, broker, market(), [FRIDAY, MONDAY], state=carried)
    result = monday.executed
    assert result.equity_before == 15_000
    assert result.positions == {"A": -75}
    assert result.orders[0].quantity == 125
    assert result.nav == 15_000


@pytest.mark.parametrize("bad_price", [None, 0, -1, float("nan"), float("inf")])
def test_entire_basket_fails_before_orders_if_execution_price_invalid(bad_price):
    fund, _ = make_fund()
    data = market(price=bad_price or 0)
    if bad_price is None:
        del data._series["A"][MONDAY]
    data._series["B"] = {FRIDAY: 100, MONDAY: 100}
    broker = SimBroker(10_000)
    broker.place_order = Mock(side_effect=AssertionError("order submitted"))
    proposal = assess_fund(fund, FRIDAY, data, ["A", "B"])
    with pytest.raises(ValueError, match="A.*2024-06-10"):
        execute_decision(fund, proposal, MONDAY, broker, data)
    broker.place_order.assert_not_called()


def test_missing_held_price_is_required_even_when_target_is_zero():
    fund, _ = make_fund(DatedAnalyst({FRIDAY: 0, "2024-06-09": 0}))
    broker = SimBroker(10_000)
    broker.place_order(Order(ticker="OLD", side="buy", quantity=1, price=100))
    broker.place_order = Mock()
    proposal = assess_fund(fund, FRIDAY, market(), ["A"])
    with pytest.raises(ValueError, match="OLD.*2024-06-10"):
        execute_decision(fund, proposal, MONDAY, broker, market())
    broker.place_order.assert_not_called()


def test_refresh_failure_does_not_fall_back_to_original_targets():
    fund, analyst = make_fund()
    original_predict = analyst.predict
    def predict(ticker, date, data):
        if date != FRIDAY:
            raise ConnectionError("refresh failed")
        return original_predict(ticker, date, data)
    analyst.predict = predict
    broker = SimBroker(10_000)
    broker.place_order = Mock()
    proposal = assess_fund(fund, FRIDAY, market(), ["A"])
    with pytest.raises(ConnectionError, match="refresh failed"):
        execute_decision(fund, proposal, MONDAY, broker, market())
    broker.place_order.assert_not_called()


def test_invalid_projected_orders_fail_before_submission(monkeypatch):
    from importlib import import_module
    pipeline = import_module("hedge_fund.pipeline.stages")
    monkeypatch.setattr(pipeline, "build_orders", lambda *args: [
        Order(ticker="A", side="buy", quantity=1000, price=200),
    ])
    fund, _ = make_fund()
    broker = SimBroker(10_000)
    broker.place_order = Mock()
    proposal = assess_fund(fund, FRIDAY, market(), ["A"])
    with pytest.raises(ValueError, match="projected position"):
        execute_decision(fund, proposal, MONDAY, broker, market())
    broker.place_order.assert_not_called()


def test_nonfinite_equity_fails_before_submission():
    fund, _ = make_fund()
    broker = SimBroker(float("nan"))
    broker.place_order = Mock()
    proposal = assess_fund(fund, FRIDAY, market(), ["A"])
    with pytest.raises(ValueError, match="equity.*finite"):
        execute_decision(fund, proposal, MONDAY, broker, market())
    broker.place_order.assert_not_called()


@pytest.mark.parametrize("hour", [10, 23])
def test_current_new_york_day_is_excluded_even_after_close(monkeypatch, hour):
    class Clock:
        @staticmethod
        def now(tz):
            return datetime(2024, 6, 10, hour, tzinfo=tz)
    monkeypatch.setattr(sessions, "datetime", Clock)
    fund, analyst = make_fund()
    broker = SimBroker(10_000)
    broker.place_order = Mock()
    with pytest.raises(ValueError, match="not complete"):
        advance(fund, FundState.initial(10_000), MONDAY, broker, market(), ["A"])
    with pytest.raises(ValueError, match="incomplete"):
        assess_fund(fund, MONDAY, market(), ["A"])
    assert analyst.calls == []
    broker.place_order.assert_not_called()
    # Yesterday is complete: the fund can still decide, and nothing executes.
    record = advance(fund, FundState.initial(10_000), "2024-06-09", broker,
                     FakeDataClient({"SPY": {"2024-06-09": 100}, "A": {"2024-06-09": 100}}), ["A"])
    assert record.decision.as_of == "2024-06-09" and record.executed is None


def test_assessment_has_no_broker_fields_and_rejects_same_day_execution():
    fund, _ = make_fund()
    proposal = assess_fund(fund, FRIDAY, market(), ["A"])
    assert DecisionRecord.model_validate_json(proposal.model_dump_json()) == proposal
    assert not {"orders", "fills", "nav"} & proposal.model_dump().keys()
    with pytest.raises(ValueError, match="must follow"):
        execute_decision(fund, proposal, FRIDAY, SimBroker(10_000), market())


def test_old_executed_record_defaults_remain_readable():
    fund, _ = make_fund()
    proposal = assess_fund(fund, FRIDAY, market(), ["A"])
    result = execute_decision(fund, proposal, MONDAY, SimBroker(10_000), market())
    raw = result.model_dump(exclude={"original_assessment", "refreshed_assessment", "execution_as_of", "execution_policy"})
    historical = CycleRecord.model_validate(raw)
    assert historical.execution_as_of is None
    assert historical.original_assessment is None
