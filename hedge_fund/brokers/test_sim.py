"""SimBroker tests — deterministic fills and bookkeeping."""

import pytest

from hedge_fund.brokers.costs import TradingCosts
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


def test_costed_fills_move_cash_by_spread_and_commission():
    costs = TradingCosts(spread_bps=5, commission_per_share=0.005)
    broker = SimBroker(cash=0.0, costs=costs)
    bought = broker.place_order(Order(ticker="AAPL", side="buy", quantity=100, price=100.0))
    assert bought.price == pytest.approx(100.05)
    assert broker.cash() == pytest.approx(-(100 * 100.05) - 0.50)
    sold = broker.place_order(Order(ticker="AAPL", side="sell", quantity=100, price=100.0))
    assert sold.price == pytest.approx(99.95)
    # A round trip at a flat price costs the full spread plus two commissions.
    assert broker.cash() == pytest.approx(-(100 * 0.10) - 1.00)
    assert broker.positions() == {}


def test_a_short_and_its_cover_pay_the_same_way():
    costs = TradingCosts(spread_bps=10, commission_per_share=0.01)
    broker = SimBroker(cash=0.0, costs=costs)
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=200.0))  # short
    assert broker.positions()["AAPL"].shares == -10
    assert broker.cash() == pytest.approx(10 * 199.80 - 0.10)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=200.0))   # cover
    assert broker.positions() == {}
    assert broker.cash() == pytest.approx(-(10 * 0.40) - 0.20)


def test_no_cost_model_fills_at_the_reference_price():
    broker = SimBroker(cash=1_000.0)
    fill = broker.place_order(Order(ticker="AAPL", side="buy", quantity=1, price=100.0))
    assert fill.price == 100.0 and broker.cash() == 900.0
