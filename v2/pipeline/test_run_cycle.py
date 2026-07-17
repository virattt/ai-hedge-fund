"""run_cycle end-to-end tests — fake data client + fake analysts + real SimBroker."""

import pytest

from v2.brokers.sim import SimBroker
from v2.data.models import Price
from v2.fund.spec import Fund, FundSpec
from v2.models import Signal
from v2.pipeline.models import CycleRecord
from v2.pipeline.run_cycle import run_cycle


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeDataClient:
    """Canned closes per ticker; a ticker absent from `closes` has no bars."""

    def __init__(self, closes):
        self._closes = closes

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        close = self._closes.get(ticker)
        if close is None:
            return []
        return [Price(open=close, close=close, high=close, low=close,
                      volume=1000, time=f"{end_date}T00:00:00Z")]


class FakeAnalyst:
    """Fixed conviction per ticker; counts predict calls."""

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


def _spec(universe=("AAPL", "MSFT", "NVDA"), max_position_pct=0.25):
    return FundSpec(
        name="test-fund",
        universe=list(universe),
        analysts=[{"name": "a"}, {"name": "b"}],
        risk={"max_position_pct": max_position_pct, "max_gross_exposure": 1.0},
        capital=100_000.0,
    )


def _fund(analysts, **spec_kwargs):
    return Fund(_spec(**spec_kwargs), analysts=analysts)


CLOSES = {"AAPL": 200.0, "MSFT": 400.0, "NVDA": 100.0}


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------

def test_full_cycle_record_is_consistent():
    fund = _fund([
        FakeAnalyst("a", views={"AAPL": 1.0, "NVDA": 0.5}),
        FakeAnalyst("b", views={"AAPL": 0.5, "MSFT": -0.5}),
    ])
    broker = SimBroker(cash=100_000.0)

    record = run_cycle(fund, "2024-06-03", broker, FakeDataClient(CLOSES))

    assert record.fund == "test-fund"
    assert record.equity_before == pytest.approx(100_000.0)
    assert len(record.signals) == 6  # 3 tickers x 2 analysts
    # Weights respect the hard caps
    for w in record.final_weights.values():
        assert abs(w) <= 0.25 + 1e-12
    # Fills mirror orders one-to-one, and the books balance
    assert len(record.fills) == len(record.orders) > 0
    assert record.nav == pytest.approx(
        record.cash + sum(s * record.marks[t] for t, s in record.positions.items())
    )
    # Bearish blended view on MSFT -> short position
    assert record.positions["MSFT"] < 0


def test_deterministic_and_json_round_trips():
    def make():
        fund = _fund([
            FakeAnalyst("a", views={"AAPL": 1.0}),
            FakeAnalyst("b", views={"MSFT": -0.5}),
        ])
        return run_cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                         FakeDataClient(CLOSES))

    first, second = make(), make()
    assert first.model_dump_json() == second.model_dump_json()
    assert CycleRecord.model_validate_json(first.model_dump_json()) == first


def test_second_cycle_rebalances_not_restarts():
    analyst = FakeAnalyst("a", views={"AAPL": 1.0})
    fund = Fund(
        FundSpec(name="f", universe=["AAPL"], analysts=[{"name": "a"}],
                 risk={"max_position_pct": 1.0, "max_gross_exposure": 1.0}),
        analysts=[analyst],
    )
    broker = SimBroker(cash=100_000.0)
    data = FakeDataClient({"AAPL": 200.0})

    first = run_cycle(fund, "2024-06-03", broker, data)
    second = run_cycle(fund, "2024-06-04", broker, data)

    assert first.positions["AAPL"] == 500  # 100k at 200
    assert second.orders == []  # already at target; nothing to trade
    assert second.positions["AAPL"] == 500


# ---------------------------------------------------------------------------
# Abstain / flat behavior
# ---------------------------------------------------------------------------

def test_all_abstain_closes_the_book_to_flat():
    views = FakeAnalyst("a", views={"AAPL": 1.0})
    fund = Fund(
        FundSpec(name="f", universe=["AAPL"], analysts=[{"name": "a"}],
                 risk={"max_position_pct": 1.0, "max_gross_exposure": 1.0}),
        analysts=[views],
    )
    broker = SimBroker(cash=100_000.0)
    data = FakeDataClient({"AAPL": 200.0})
    run_cycle(fund, "2024-06-03", broker, data)
    assert broker.positions()["AAPL"].shares == 500

    views._abstain = True
    record = run_cycle(fund, "2024-06-04", broker, data)

    assert record.positions == {}  # book closed to flat
    assert record.nav == pytest.approx(100_000.0)  # flat closes at same price


# ---------------------------------------------------------------------------
# Pricing edge cases
# ---------------------------------------------------------------------------

def test_unpriced_unowned_ticker_skipped_and_analysts_never_called():
    analyst = FakeAnalyst("a", views={"AAPL": 1.0})
    fund = _fund([analyst, FakeAnalyst("b")])
    closes = dict(CLOSES)
    del closes["NVDA"]

    record = run_cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                       FakeDataClient(closes))

    assert [s.ticker for s in record.skipped] == ["NVDA"]
    assert "NVDA" not in analyst.predict_calls
    assert "NVDA" not in record.final_weights


def test_unpriced_held_ticker_raises():
    broker = SimBroker(cash=100_000.0)
    fund = _fund([FakeAnalyst("a", views={"AAPL": 1.0}), FakeAnalyst("b")])
    run_cycle(fund, "2024-06-03", broker, FakeDataClient(CLOSES))
    assert broker.positions()  # something is held

    closes = {t: c for t, c in CLOSES.items() if t not in broker.positions()}
    with pytest.raises(ValueError, match="cannot value the book"):
        run_cycle(fund, "2024-06-04", broker, FakeDataClient(closes))


def test_analyst_error_propagates():
    """Fail loud: an infrastructure failure must not become a quiet no-trade."""
    fund = _fund([FakeAnalyst("a", error=ConnectionError("API down")),
                  FakeAnalyst("b")])
    with pytest.raises(ConnectionError):
        run_cycle(fund, "2024-06-03", SimBroker(cash=100_000.0),
                  FakeDataClient(CLOSES))
