"""Stage tests — assess then execute, with fake data, fake analysts, a real SimBroker."""

from datetime import date as _date
from datetime import timedelta
from math import log, sqrt
from statistics import stdev

import pytest

from hedge_fund.brokers.sim import SimBroker
from hedge_fund.data.models import Price
from hedge_fund.fund.spec import Fund, FundSpec
from hedge_fund.models import Signal
from hedge_fund.pipeline.models import Allocated, AllocationRecord, CycleRecord
from hedge_fund.pipeline.stages import assess_fund, execute_decision, history_start, liquidity


def _cycle(fund, as_of, broker, data, universe):
    """Assess as of *as_of* and execute at the next day's close — one full
    decision-to-fills cycle, the way `advance` sequences the two stages."""
    decision = assess_fund(fund, as_of, data, universe)
    session = (_date.fromisoformat(as_of) + timedelta(days=1)).isoformat()
    return execute_decision(fund, decision, session, broker, data)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeDataClient:
    """Canned closes per ticker; a ticker absent from `closes` has no bars."""

    def __init__(self, closes):
        self._closes = closes

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        if ticker == "SPY":
            return [Price(open=100, close=100, high=100, low=100, volume=1000,
                          time=f"{start_date}T00:00:00Z")]
        close = self._closes.get(ticker)
        if close is None:
            return []
        return [Price(open=close, close=close, high=close, low=close,
                      volume=1000, time=f"{end_date}T00:00:00Z")]


class FakeAnalyst:
    """Fixed conviction per ticker; counts predict calls."""

    investment_approach = "long_short"
    horizon_days = 1

    def __init__(self, name, views=None, abstain=False, error=None):
        self._name = name
        self._views = views or {}
        self._abstain = abstain
        self._error = error
        self.predict_calls = []

    @property
    def name(self):
        return self._name

    def predict(self, ticker, date, data_client):
        self.predict_calls.append(ticker)
        if self._error is not None:
            raise self._error
        metadata = {"abstained": True} if self._abstain else {}
        value = 0.0 if self._abstain else self._views.get(ticker, 0.0)
        return Signal(model_name=self._name, ticker=ticker, date=date,
                      value=value, metadata=metadata)


@pytest.fixture(autouse=True)
def registered_fakes(monkeypatch):
    from hedge_fund.signals import ALPHA_MODEL_REGISTRY
    for name in ("a", "b"):
        monkeypatch.setitem(ALPHA_MODEL_REGISTRY, name, FakeAnalyst)


def _spec(strategies=None, max_position_pct=0.25):
    if strategies is None:
        strategies = [{"name": "solo", "models": [{"name": "a"}]}]
    strategies = [{"blend": {"mode": "long_short"}, **s} for s in strategies]
    return FundSpec(
        schema_version=2,
        name="test-fund",
        strategies=strategies,
        risk={"max_position_pct": max_position_pct, "max_gross_exposure": 1.0},
        costs={"spread_bps": 0, "commission_per_share": 0},  # exact arithmetic below
        capital=100_000.0,
    )


CLOSES = {"AAPL": 200.0, "MSFT": 400.0, "NVDA": 100.0}
# What to trade is a run-time argument, not a mandate field.
UNIVERSE = ["AAPL", "MSFT", "NVDA"]


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------

def test_full_cycle_record_is_consistent():
    spec = _spec(strategies=[
        {"name": "long", "models": [{"name": "a"}]},
        {"name": "short", "models": [{"name": "b"}]},
    ])
    fund = Fund(spec, models={
        "long": [FakeAnalyst("a", views={"AAPL": 1.0, "NVDA": 0.5})],
        "short": [FakeAnalyst("b", views={"MSFT": -1.0})],
    })
    broker = SimBroker(cash=100_000.0)

    record = _cycle(fund, "2024-06-03", broker, FakeDataClient(CLOSES),
                       UNIVERSE)

    assert record.fund == "test-fund"
    assert record.schema_version == 2
    assert record.equity_before == pytest.approx(100_000.0)
    assert len(record.strategies) == 2
    assert all(len(sr.signals) == 3 for sr in record.strategies)  # 3 tickers x 1 analyst
    # The engine stamps each model's declared horizon on its views.
    assert all(sig.horizon_days == 1 for sr in record.strategies for sig in sr.signals)
    # Weights respect the hard caps
    for w in record.final_weights.values():
        assert abs(w) <= 0.25 + 1e-12
    # Fills mirror orders one-to-one, and the books balance
    assert len(record.fills) == len(record.orders) > 0
    assert record.nav == pytest.approx(
        record.cash + sum(s * record.marks[t] for t, s in record.positions.items())
    )
    # The short strategy's bearish view -> short position
    assert record.positions["MSFT"] < 0


def test_netting_math_two_strategies_unequal_slices():
    """Two sleeves, overlapping ticker, 3:1 slices — hand-computed netting."""
    spec = _spec(strategies=[
        {"name": "s1", "weight": 3.0, "models": [{"name": "a"}]},
        {"name": "s2", "weight": 1.0, "models": [{"name": "b"}]},
    ], max_position_pct=1.0)
    fund = Fund(spec, models={
        # s1 sleeve: AAPL 0.5, MSFT 0.5 (equal convictions, gross 1.0)
        "s1": [FakeAnalyst("a", views={"AAPL": 1.0, "MSFT": 1.0})],
        # s2 sleeve: MSFT -1.0 (only conviction takes full gross)
        "s2": [FakeAnalyst("b", views={"MSFT": -1.0})],
    })

    record = _cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                       FakeDataClient(CLOSES), UNIVERSE)

    s1, s2 = record.strategies
    assert s1.slice == pytest.approx(0.75)
    assert s2.slice == pytest.approx(0.25)
    assert s1.weights == {"AAPL": pytest.approx(0.5), "MSFT": pytest.approx(0.5),
                          "NVDA": 0.0}
    assert s2.weights["MSFT"] == pytest.approx(-1.0)
    # Netted: AAPL = .75*.5 = .375 ; MSFT = .75*.5 + .25*(-1) = .125
    assert record.target_weights["AAPL"] == pytest.approx(0.375)
    assert record.target_weights["MSFT"] == pytest.approx(0.125)


def test_an_allocation_replaces_the_mandate_slices_and_blend_weights():
    spec = _spec(strategies=[
        {"name": "s1", "weight": 3.0, "models": [{"name": "a"}, {"name": "b"}]},
        {"name": "s2", "weight": 1.0, "models": [{"name": "a"}]},
    ], max_position_pct=1.0)
    fund = Fund(spec, models={
        "s1": [FakeAnalyst("a", views={"AAPL": 1.0}), FakeAnalyst("b", views={"AAPL": 0.0})],
        "s2": [FakeAnalyst("a", views={"MSFT": -1.0})],
    })
    one = Allocated(mandate=1.0, t_stat=None, n=0, weight=1.0)
    allocation = AllocationRecord(
        as_of="2024-06-03",
        strategies={"s1": Allocated(mandate=3.0, t_stat=-3.0, n=20, weight=0.75), "s2": one},
        models={"s1": {"a": Allocated(mandate=1.0, t_stat=2.0, n=20, weight=3.0), "b": one}, "s2": {"a": one}},
    )
    decision = assess_fund(fund, "2024-06-03", FakeDataClient(CLOSES), UNIVERSE, allocation=allocation)
    s1, s2 = decision.strategies
    # Slices come from the allocated 0.75 : 1, not the mandate's 3 : 1.
    assert (s1.slice, s2.slice) == (pytest.approx(0.75 / 1.75), pytest.approx(1 / 1.75))
    # a at weight 3 and b at weight 1 vote 1.0 and 0.0: conviction 0.75, not the equal-weight 0.5.
    assert s1.convictions["AAPL"] == pytest.approx(0.75)
    assert decision.allocation == allocation
    plain = assess_fund(fund, "2024-06-03", FakeDataClient(CLOSES), UNIVERSE)
    assert plain.strategies[0].convictions["AAPL"] == pytest.approx(0.5) and plain.allocation is None
    assert "allocation" not in plain.model_dump() and "allocation" in decision.model_dump()
    # A refresh across a calendar gap re-asks with the same allocation.
    wednesday = assess_fund(fund, "2024-06-05", FakeDataClient(CLOSES), UNIVERSE, allocation=allocation)
    record = execute_decision(fund, wednesday, "2024-06-07", SimBroker(cash=100_000.0), FakeDataClient(CLOSES))
    assert record.refreshed_assessment.as_of == "2024-06-06"
    assert record.refreshed_assessment.allocation == allocation and record.allocation == allocation


def test_slices_normalize():
    """weights 2/2 must mean exactly the same as 1/1."""
    def run(w1, w2):
        spec = _spec(strategies=[
            {"name": "s1", "weight": w1, "models": [{"name": "a"}]},
            {"name": "s2", "weight": w2, "models": [{"name": "b"}]},
        ])
        fund = Fund(spec, models={
            "s1": [FakeAnalyst("a", views={"AAPL": 1.0})],
            "s2": [FakeAnalyst("b", views={"NVDA": -0.5})],
        })
        return _cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                         FakeDataClient(CLOSES), UNIVERSE)

    assert run(2.0, 2.0).target_weights == run(1.0, 1.0).target_weights


def test_deterministic_and_json_round_trips():
    def make():
        spec = _spec()
        fund = Fund(spec, models={
            "solo": [FakeAnalyst("a", views={"AAPL": 1.0, "MSFT": -0.5})],
        })
        return _cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                         FakeDataClient(CLOSES), UNIVERSE)

    first, second = make(), make()
    assert first.model_dump_json() == second.model_dump_json()
    assert CycleRecord.model_validate_json(first.model_dump_json()) == first


def test_second_cycle_rebalances_not_restarts():
    analyst = FakeAnalyst("a", views={"AAPL": 1.0})
    fund = Fund(_spec(max_position_pct=1.0), models={"solo": [analyst]})
    broker = SimBroker(cash=100_000.0)
    data = FakeDataClient({"AAPL": 200.0})

    first = _cycle(fund, "2024-06-03", broker, data, ["AAPL"])
    second = _cycle(fund, "2024-06-04", broker, data, ["AAPL"])

    assert first.positions["AAPL"] == 500  # 100k at 200
    assert second.orders == []  # already at target; nothing to trade
    assert second.positions["AAPL"] == 500


# ---------------------------------------------------------------------------
# Abstain / flat behavior
# ---------------------------------------------------------------------------

def test_all_abstain_closes_the_book_to_flat():
    analyst = FakeAnalyst("a", views={"AAPL": 1.0})
    fund = Fund(_spec(max_position_pct=1.0), models={"solo": [analyst]})
    broker = SimBroker(cash=100_000.0)
    data = FakeDataClient({"AAPL": 200.0})
    _cycle(fund, "2024-06-03", broker, data, ["AAPL"])
    assert broker.positions()["AAPL"].shares == 500

    analyst._abstain = True
    record = _cycle(fund, "2024-06-04", broker, data, ["AAPL"])

    assert record.positions == {}  # book closed to flat
    assert record.nav == pytest.approx(100_000.0)  # flat closes at same price


# ---------------------------------------------------------------------------
# Pricing edge cases
# ---------------------------------------------------------------------------

def test_unpriced_unowned_ticker_skipped_and_analysts_never_called():
    analyst = FakeAnalyst("a", views={"AAPL": 1.0})
    fund = Fund(_spec(), models={"solo": [analyst]})
    closes = dict(CLOSES)
    del closes["NVDA"]

    record = _cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                       FakeDataClient(closes), UNIVERSE)

    assert [s.ticker for s in record.skipped] == ["NVDA"]
    assert "NVDA" not in analyst.predict_calls
    assert "NVDA" not in record.final_weights


def test_unpriced_held_ticker_raises():
    broker = SimBroker(cash=100_000.0)
    fund = Fund(_spec(), models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    _cycle(fund, "2024-06-03", broker, FakeDataClient(CLOSES), UNIVERSE)
    assert broker.positions()  # something is held

    closes = {t: c for t, c in CLOSES.items() if t not in broker.positions()}
    with pytest.raises(ValueError, match="cannot value the book"):
        _cycle(fund, "2024-06-04", broker, FakeDataClient(closes), UNIVERSE)


def test_universe_is_a_run_time_argument():
    """The same fund, pointed at different names, trades different names —
    and the record says what it was asked to trade."""
    fund = Fund(_spec(max_position_pct=1.0), models={
        "solo": [FakeAnalyst("a", views={"AAPL": 1.0, "MSFT": 1.0})],
    })

    record = _cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                       FakeDataClient(CLOSES), ["aapl", "AAPL"])

    assert record.universe == ["AAPL"]  # upper-cased and de-duped
    assert "MSFT" not in record.final_weights


def test_empty_universe_raises():
    fund = Fund(_spec(), models={"solo": [FakeAnalyst("a")]})
    with pytest.raises(ValueError, match="universe is empty"):
        _cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                  FakeDataClient(CLOSES), [])


def test_analyst_error_propagates():
    """Fail loud: an infrastructure failure must not become a quiet no-trade."""
    fund = Fund(_spec(), models={
        "solo": [FakeAnalyst("a", error=ConnectionError("API down"))],
    })
    with pytest.raises(ConnectionError):
        _cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                  FakeDataClient(CLOSES), UNIVERSE)


def test_changed_mode_is_enforced_on_next_cycle():
    fund = Fund(_spec(), models={"solo": [FakeAnalyst("a", views={"AAPL": -.8})]})
    fund.spec.strategies[0].blend.mode = "long_only"
    record = _cycle(fund, "2024-06-03", SimBroker(cash=100_000), FakeDataClient(CLOSES), UNIVERSE)
    assert record.orders == []
    assert record.final_weights == dict.fromkeys(UNIVERSE, 0)


def _rule_fund(mode, names=("buffett", "druckenmiller"), views=None, **risk):
    spec = FundSpec(
        schema_version=2, name="rules", strategies=[{
            "name": "team", "models": [{"name": name} for name in names],
            "blend": {"mode": mode},
        }], risk={"max_position_pct": .25, "max_gross_exposure": 1, **risk},
        costs={"spread_bps": 0, "commission_per_share": 0},
    )
    views = views or {name: {"A": .8, "B": -.6} for name in names}
    return Fund(spec, models={"team": [FakeAnalyst(name, views[name]) for name in names]})


@pytest.mark.parametrize("mode", ["long_only", "long_short", "dollar_neutral"])
def test_all_modes_execute_and_preserve_complete_records(mode):
    fund = _rule_fund(mode)
    record = _cycle(fund, "2024-06-03", SimBroker(100_000), FakeDataClient({"A": 100, "B": 200}), ["A", "B"])
    strategy = record.strategies[0]
    assert strategy.convictions == pytest.approx({"A": .8, "B": -.6})
    assert strategy.eligible_scores == pytest.approx({"A": .8, "B": 0 if mode == "long_only" else -.3})
    if mode == "long_only":
        assert record.positions == {"A": 250}
    else:
        assert record.positions == {"A": 250, "B": -125}
    assert strategy.final_contribution == record.final_weights
    assert record.nav == 100_000
    assert CycleRecord.model_validate_json(record.model_dump_json()) == record
    old_fields = record.model_dump()
    old_fields.pop("risk_scale_factor")
    for sr in old_fields["strategies"]:
        for field in ("eligible_scores", "flat_reason", "final_contribution"):
            sr.pop(field)
    readable = CycleRecord.model_validate(old_fields)
    assert readable.strategies[0].eligible_scores == {}
    assert readable.risk_scale_factor is None


def test_neutral_flat_strategy_reserves_capital_and_closes_prior_exposure():
    spec = _spec([
        {"name": "neutral", "weight": 3, "models": [{"name": "a"}], "blend": {"mode": "dollar_neutral"}},
        {"name": "owner", "weight": 1, "models": [{"name": "b"}], "blend": {"mode": "long_only"}},
    ], max_position_pct=1)
    model = FakeAnalyst("a", {"A": 1, "B": -1})
    fund = Fund(spec, models={"neutral": [model], "owner": [FakeAnalyst("b", {"C": 1})]})
    broker = SimBroker(100_000)
    data = FakeDataClient({"A": 100, "B": 100, "C": 100})
    first = _cycle(fund, "2024-06-03", broker, data, ["A", "B", "C"])
    assert first.positions == {"A": 375, "B": -375, "C": 250}
    model._views = {"A": 1, "B": .2}
    second = _cycle(fund, "2024-06-04", broker, data, ["A", "B", "C"])
    assert second.strategies[0].flat_reason == "missing_short_side"
    assert second.positions == {"C": 250}
    assert second.cash == 75_000
    assert {o.ticker for o in second.orders} == {"A", "B"}


def test_neutral_fund_scaling_preserves_sleeves_with_overlap():
    spec = _spec([
        {"name": "neutral", "weight": 3, "models": [{"name": "a"}], "blend": {"mode": "dollar_neutral"}},
        {"name": "owner", "weight": 1, "models": [{"name": "b"}], "blend": {"mode": "long_only"}},
    ])
    fund = Fund(spec, models={"neutral": [FakeAnalyst("a", {"A": 1, "B": -1})],
                            "owner": [FakeAnalyst("b", {"A": 1})]})
    record = _cycle(fund, "2024-06-03", SimBroker(100_000), FakeDataClient({"A": 100, "B": 100}), ["A", "B"])
    assert record.target_weights == {"A": .625, "B": -.375}
    assert record.risk_scale_factor == .4
    neutral, owner = record.strategies
    assert neutral.final_contribution == pytest.approx({"A": .15, "B": -.15})
    assert owner.final_contribution == pytest.approx({"A": .1, "B": 0})
    assert record.final_weights == pytest.approx({"A": .25, "B": -.15})
    assert sum(record.final_weights.values()) == pytest.approx(.1)  # only the neutral strategy must balance


def test_clipping_attribution_preserves_exactly_offset_contributions():
    spec = _spec([
        {"name": "s1", "models": [{"name": "a"}]},
        {"name": "s2", "models": [{"name": "b"}]},
    ], max_position_pct=.2)
    fund = Fund(spec, models={"s1": [FakeAnalyst("a", {"A": 1, "B": 1})],
                            "s2": [FakeAnalyst("b", {"A": -1, "B": 1})]})
    record = _cycle(fund, "2024-06-03", SimBroker(100_000), FakeDataClient({"A": 100, "B": 100}), ["A", "B"])
    assert record.risk_scale_factor is None
    assert record.final_weights == {"A": 0, "B": .2}
    assert record.strategies[0].final_contribution == {"A": .25, "B": .1}
    assert record.strategies[1].final_contribution == {"A": -.25, "B": .1}


def test_whole_share_rounding_keeps_target_neutral_without_changing_orders():
    fund = _rule_fund("dollar_neutral", max_position_pct=1)
    record = _cycle(fund, "2024-06-03", SimBroker(10_000), FakeDataClient({"A": 300, "B": 700}), ["A", "B"])
    assert record.final_weights == {"A": .5, "B": -.5}
    assert [(o.ticker, o.side, o.quantity) for o in record.orders] == [("B", "sell", 7), ("A", "buy", 16)]
    assert sum(record.positions[t] * record.marks[t] for t in record.positions) == -100


@pytest.mark.parametrize("case,expected", [
    ("nonfinite", "finite"), ("neutrality", "dollar-neutral"),
    ("position", "max_position_pct"), ("gross", "max_gross_exposure"),
    ("contributions", "contributions do not sum"),
])
def test_invalid_risk_output_never_reaches_broker(monkeypatch, case, expected):
    from importlib import import_module
    from unittest.mock import Mock

    from hedge_fund.risk.limits import RiskResult
    pipeline = import_module("hedge_fund.pipeline.stages")
    mode = "dollar_neutral" if case in ("neutrality", "contributions") else "long_short"
    fund = _rule_fund(mode, max_gross_exposure=.3 if case == "gross" else 1)
    targets = {"A": .25, "B": -.25}
    factor = None
    if case == "nonfinite":
        targets["A"] = float("nan")
    elif case == "neutrality":
        targets["B"] = -.1
    elif case == "position":
        targets["A"] = .4
    elif case == "contributions":
        factor = .4  # recorded contributions will disagree with final weights
    monkeypatch.setattr(pipeline, "apply_limits", lambda *args, **kwargs: RiskResult(weights=targets, clamps=[], scale_factor=factor))
    broker = SimBroker(100_000)
    broker.place_order = Mock(side_effect=AssertionError("invalid orders reached broker"))
    with pytest.raises(ValueError, match=expected):
        _cycle(fund, "2024-06-03", broker, FakeDataClient({"A": 100, "B": 100}), ["A", "B"])
    broker.place_order.assert_not_called()


@pytest.mark.parametrize("mode,expected", [("long_only", "long-only"), ("long_short", "short evidence")])
def test_invalid_short_targets_never_reach_broker(monkeypatch, mode, expected):
    from importlib import import_module
    from unittest.mock import Mock
    pipeline = import_module("hedge_fund.pipeline.stages")
    original = pipeline.blend_signals
    def invalid_blend(*args, **kwargs):
        result = original(*args, **kwargs)
        result.weights["A"] = -1
        return result
    monkeypatch.setattr(pipeline, "blend_signals", invalid_blend)
    fund = _rule_fund(mode, names=("buffett",), views={"buffett": {"A": -.8}})
    broker = SimBroker(100_000)
    broker.place_order = Mock(side_effect=AssertionError("invalid orders reached broker"))
    with pytest.raises(ValueError, match=expected):
        _cycle(fund, "2024-06-03", broker, FakeDataClient({"A": 100}), ["A"])
    broker.place_order.assert_not_called()


def test_strategy_gross_violation_is_rejected_even_when_fund_risk_clips_it(monkeypatch):
    from importlib import import_module
    from unittest.mock import Mock
    pipeline = import_module("hedge_fund.pipeline.stages")
    original = pipeline.blend_signals
    def invalid_blend(*args, **kwargs):
        result = original(*args, **kwargs)
        result.weights = {"A": 1, "B": -1}
        return result
    monkeypatch.setattr(pipeline, "blend_signals", invalid_blend)
    fund = _rule_fund("long_short")
    broker = SimBroker(100_000)
    broker.place_order = Mock(side_effect=AssertionError("invalid orders reached broker"))
    with pytest.raises(ValueError, match="team.*strategy gross target"):
        _cycle(fund, "2024-06-03", broker, FakeDataClient({"A": 100, "B": 100}), ["A", "B"])
    broker.place_order.assert_not_called()


def test_history_start_is_thirty_days_before():
    assert history_start("2025-01-15") == "2024-12-16"


def test_a_close_older_than_a_week_does_not_mark():
    class StaleDataClient(FakeDataClient):
        def get_prices(self, ticker, start_date, end_date, **kwargs):
            # One bar, ten days before the date asked for: inside the history
            # window, outside the mark's freshness.
            stale = (_date.fromisoformat(end_date) - timedelta(days=10)).isoformat()
            return [Price(open=1, close=1, high=1, low=1, volume=1, time=f"{stale}T00:00:00Z")]

    decision = assess_fund(Fund(_spec(), models={"solo": [FakeAnalyst("a", views={})]}),
                           "2024-06-03", StaleDataClient({}), ["AAPL"])
    assert decision.marks == {} and [s.ticker for s in decision.skipped] == ["AAPL"]


# ---------------------------------------------------------------------------
# The volume cap
# ---------------------------------------------------------------------------

class VolumeDataClient(FakeDataClient):
    """Canned closes plus a daily volume series per ticker."""

    def __init__(self, closes, volumes):
        super().__init__(closes)
        self._volumes = volumes

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        if ticker not in self._volumes:
            return super().get_prices(ticker, start_date, end_date, **kwargs)
        close = self._closes[ticker]
        end = _date.fromisoformat(end_date)
        return [Price(open=close, close=close, high=close, low=close, volume=v,
                      time=f"{(end - timedelta(days=len(self._volumes[ticker]) - 1 - i)).isoformat()}T00:00:00Z")
                for i, v in enumerate(self._volumes[ticker])]


class SeriesDataClient(FakeDataClient):
    """Canned (close, volume) daily series per ticker, ending on the date asked for."""

    def __init__(self, closes, series):
        super().__init__(closes)
        self._series = series

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        if ticker not in self._series:
            return super().get_prices(ticker, start_date, end_date, **kwargs)
        end = _date.fromisoformat(end_date)
        return [Price(open=c, close=c, high=c, low=c, volume=v,
                      time=f"{(end - timedelta(days=len(self._series[ticker]) - 1 - i)).isoformat()}T00:00:00Z")
                for i, (c, v) in enumerate(self._series[ticker])]


def test_liquidity_is_the_mean_volume_of_the_last_twenty_bars():
    data = VolumeDataClient(CLOSES, {"AAPL": [1_000_000] * 5 + [2_000_000] * 20, "MSFT": [500] * 3})
    liquid = liquidity(["AAPL", "MSFT", "ZZZ"], "2024-06-04", data)
    assert sorted(liquid) == ["AAPL", "MSFT"]   # ZZZ has no bars: absent
    assert liquid["AAPL"].adv == pytest.approx(2_000_000) and liquid["MSFT"].adv == pytest.approx(500)
    assert liquid["AAPL"].volatility == 0.0   # a flat series has no vol


def test_liquidity_volatility_is_the_sample_sigma_of_daily_log_returns():
    data = SeriesDataClient(CLOSES, {"AAPL": [(100.0, 1_000), (110.0, 2_000), (100.0, 3_000)]})
    liquid = liquidity(["AAPL", "MSFT"], "2024-06-04", data)
    assert liquid["AAPL"].adv == pytest.approx(2_000)
    assert liquid["AAPL"].volatility == pytest.approx(stdev([log(1.1), log(100 / 110)]))
    assert liquid["MSFT"].volatility == 0.0   # one bar: no return to measure


def test_the_fill_pays_square_root_impact_and_the_cycle_derives_it():
    fund = Fund(_spec(), models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    data = SeriesDataClient(CLOSES, {"AAPL": [(100.0, 1_000), (110.0, 2_000), (100.0, 3_000)]})
    broker = SimBroker(cash=100_000.0, costs=fund.spec.costs)   # spread and commission 0: impact alone
    record = _cycle(fund, "2024-06-03", broker, data, UNIVERSE)
    [order], [fill] = record.orders, record.fills
    assert (order.ticker, order.price, order.adv) == ("AAPL", 100.0, 2_000.0)
    sigma = stdev([log(1.1), log(100 / 110)])
    impact = sigma * sqrt(order.quantity / 2_000)
    assert fill.price == pytest.approx(100.0 * (1 + impact))
    assert record.spread_cost == 0.0
    assert record.impact == pytest.approx(order.quantity * 100.0 * impact)
    assert record.trading_cost == pytest.approx(record.impact)


def test_volume_cap_clips_the_order_and_records_the_clamp():
    spec = FundSpec(**{**_spec().model_dump(), "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1.0, "max_adv_pct": 0.05}})
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0, "MSFT": 1.0})]})
    # AAPL: 20-day ADV 1,000 -> cap 50 shares; the target is 25% of 100k at 200 = 125.
    # MSFT: ADV 100,000 -> cap 5,000, so its 62-share target (25% of 100k at 400) is untouched.
    data = VolumeDataClient(CLOSES, {"AAPL": [1_000] * 20, "MSFT": [100_000] * 20})
    record = _cycle(fund, "2024-06-03", SimBroker(cash=100_000.0), data, UNIVERSE)
    assert {o.ticker: o.quantity for o in record.orders} == {"AAPL": 50, "MSFT": 62}
    assert record.positions == {"AAPL": 50, "MSFT": 62}
    liquidity = [c for c in record.clamps if c.limit == "max_adv_pct"]
    assert [(c.ticker, c.before, c.after) for c in liquidity] == [("AAPL", pytest.approx(0.25), pytest.approx(0.10))]
    assert record.final_weights["AAPL"] == pytest.approx(0.25)   # the decision is untouched; only the fill is capped


# ---------------------------------------------------------------------------
# The halving tier and the factor limits
# ---------------------------------------------------------------------------

from math import exp  # noqa: E402

from hedge_fund.data.models import CompanyFacts  # noqa: E402
from hedge_fund.pipeline.stages import history_days  # noqa: E402


def _risk_spec(**risk):
    return FundSpec(**{**_spec().model_dump(), "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1.0, **risk}})


class FactorDataClient(FakeDataClient):
    """Eighty-one daily bars per ticker from canned log returns, ending on the
    date asked for; records every window it was asked for."""

    MARKET = [0.01 if i % 2 == 0 else -0.01 for i in range(80)]

    def __init__(self, closes, multipliers, sectors):
        super().__init__(closes)
        self._multipliers = multipliers
        self._sectors = sectors
        self.windows = []

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        self.windows.append((ticker, start_date, end_date))
        multiplier = 1.0 if ticker == "SPY" else self._multipliers.get(ticker)
        if multiplier is None:
            return super().get_prices(ticker, start_date, end_date, **kwargs)
        end = _date.fromisoformat(end_date)
        closes = [self._closes.get(ticker, 100.0)]
        for r in self.MARKET:
            closes.append(closes[-1] * exp(multiplier * r))
        return [Price(open=c, close=c, high=c, low=c, volume=1000,
                      time=f"{(end - timedelta(days=len(closes) - 1 - i)).isoformat()}T00:00:00Z")
                for i, c in enumerate(closes)]

    def get_company_facts(self, ticker):
        return CompanyFacts(ticker=ticker, sector=self._sectors.get(ticker))


def test_the_halving_tier_halves_the_book_and_records_the_drawdown():
    fund = Fund(_risk_spec(max_position_pct=1.0, halve_drawdown_pct=0.10, max_drawdown_pct=0.20),
                models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0, "MSFT": -0.5})]})
    full = assess_fund(fund, "2024-06-03", FakeDataClient(CLOSES), UNIVERSE)
    halved = assess_fund(fund, "2024-06-03", FakeDataClient(CLOSES), UNIVERSE, drawdown=0.12)
    assert full.drawdown == 0.0 and full.clamps == []
    assert halved.drawdown == 0.12
    assert [(c.limit, c.before, c.after) for c in halved.clamps] == [("halve_drawdown_pct", 0.12, 0.5)]
    assert halved.final_weights == {t: pytest.approx(w / 2) for t, w in full.final_weights.items()}
    for record in halved.strategies:
        assert record.final_contribution == {t: pytest.approx(w / 2) for t, w in full.strategies[0].final_contribution.items()}
    # Without the tier the decision does not carry a drawdown at all.
    plain = assess_fund(Fund(_spec(), models={"solo": [FakeAnalyst("a")]}), "2024-06-03", FakeDataClient(CLOSES), UNIVERSE)
    assert plain.drawdown is None and "drawdown" not in plain.model_dump() and "exposures" not in plain.model_dump()


def test_a_refresh_across_a_gap_keeps_the_original_drawdown():
    fund = Fund(_risk_spec(max_position_pct=1.0, halve_drawdown_pct=0.10),
                models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    friday = assess_fund(fund, "2024-06-07", FakeDataClient(CLOSES), UNIVERSE, drawdown=0.12)
    cycle = execute_decision(fund, friday, "2024-06-10", SimBroker(cash=100_000.0), FakeDataClient(CLOSES))
    assert cycle.refreshed_assessment.as_of == "2024-06-09"
    assert cycle.refreshed_assessment.drawdown == 0.12 and cycle.drawdown == 0.12
    assert [c.limit for c in cycle.clamps] == ["halve_drawdown_pct"]


def test_a_factor_limit_fits_the_model_on_a_quarter_of_bars_and_records_it():
    spec = _risk_spec(max_position_pct=1.0, max_beta=0.01, max_sector_pct=0.3)
    assert history_days(spec) == 100 and history_days(_spec()) == 30
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    data = FactorDataClient(CLOSES, {"AAPL": 2.0, "MSFT": 1.0}, {"AAPL": "Technology"})
    decision = assess_fund(fund, "2024-06-03", data, UNIVERSE)
    model = decision.exposures
    assert model is not None and model.as_of == "2024-06-03"
    assert model.names["AAPL"].beta == pytest.approx(0.67 * 2 + 0.33) and model.names["AAPL"].n_bars == 80
    assert model.names["AAPL"].sector == "Technology" and model.names["MSFT"].sector is None
    assert model.names["NVDA"].beta == 1.0 and model.names["NVDA"].n_bars == 0   # one bar: the prior
    # The whole book sits in AAPL: Technology is over its cap, then beta is.
    sector, beta = decision.clamps
    assert (sector.limit, sector.sector, sector.before, sector.after) == ("max_sector_pct", "Technology", 1.0, pytest.approx(0.3))
    assert (beta.limit, beta.before) == ("max_beta", pytest.approx(0.3 * (0.67 * 2 + 0.33)))
    assert decision.final_weights["AAPL"] == pytest.approx(0.01 / (0.67 * 2 + 0.33))
    # Marks, liquidity, and the model all fetch the one 100-day window.
    assert {start for _, start, _ in data.windows} == {history_start("2024-06-03", 100)}
    assert decision.model_dump()["exposures"]["names"]["AAPL"]["sector"] == "Technology"
