"""SimBroker tests — deterministic fills and bookkeeping."""

import pytest

from hedge_fund.brokers.models import Order
from hedge_fund.brokers.sim import SimBroker


def test_buy_updates_cash_and_position():
    broker = SimBroker(cash=10_000.0)
    fill = broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    assert broker.cash() == pytest.approx(9_000.0)
    assert broker.positions()["AAPL"].shares == 10
    assert fill.quantity == 10
    assert fill.price == 100.0


def test_sell_updates_cash_and_position():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=4, price=110.0))
    assert broker.positions()["AAPL"].shares == 6
    assert broker.cash() == pytest.approx(-1_000.0 + 440.0)


def test_position_removed_at_zero():
    broker = SimBroker(cash=1_000.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=5, price=100.0))
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=5, price=100.0))
    assert broker.positions() == {}


def test_sell_past_zero_creates_short():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=3, price=100.0))
    assert broker.positions()["AAPL"].shares == -3
    assert broker.cash() == pytest.approx(300.0)


def test_nonpositive_price_raises():
    broker = SimBroker(cash=1_000.0)
    with pytest.raises(ValueError):
        broker.place_order(Order(ticker="AAPL", side="buy", quantity=1, price=0.0))


@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_price_raises_without_mutating_book(price):
    broker = SimBroker(cash=1_000.0)
    with pytest.raises(ValueError):
        broker.place_order(Order(ticker="AAPL", side="buy", quantity=1, price=price))
    assert broker.cash() == 1_000.0
    assert broker.positions() == {}


def test_positions_returns_a_copy():
    broker = SimBroker(cash=1_000.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=5, price=100.0))
    broker.positions().clear()
    assert broker.positions()["AAPL"].shares == 5


def test_slippage_moves_the_fill_against_the_order():
    broker = SimBroker(cash=10_000.0, slippage_bps=10)  # 10 bps = 0.1%
    buy = broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    assert buy.price == pytest.approx(100.1)
    assert broker.cash() == pytest.approx(10_000.0 - 10 * 100.1)

    sell = broker.place_order(Order(ticker="AAPL", side="sell", quantity=4, price=110.0))
    assert sell.price == pytest.approx(109.89)
    assert broker.cash() == pytest.approx(10_000.0 - 10 * 100.1 + 4 * 109.89)


def test_commission_leaves_cash_but_not_the_price():
    broker = SimBroker(cash=10_000.0, commission_bps=5)  # 5 bps of notional per fill
    buy = broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    assert buy.price == pytest.approx(100.0)
    assert broker.cash() == pytest.approx(10_000.0 - 1_000.0 - 0.5)

    sell = broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=100.0))
    assert sell.price == pytest.approx(100.0)
    # round trip on flat prices costs exactly two commissions, nothing else
    assert broker.cash() == pytest.approx(10_000.0 - 1.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"commission_bps": -1},
        {"slippage_bps": -1},
        {"commission_bps": float("nan")},
        {"slippage_bps": float("inf")},
        {"slippage_bps": 10_000},
    ],
)
def test_costs_that_could_poison_a_fill_raise(kwargs):
    """A sell at >= 100% slippage prices the fill at or below zero, and
    place_order only checks the reference price — so the guard lives here."""
    with pytest.raises(ValueError):
        SimBroker(cash=1_000.0, **kwargs)
