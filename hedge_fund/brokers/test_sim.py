"""SimBroker tests — deterministic fills and bookkeeping."""

import pytest

from hedge_fund.brokers.models import Commission, Order
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


def test_positions_returns_a_copy():
    broker = SimBroker(cash=1_000.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=5, price=100.0))
    broker.positions().clear()
    assert broker.positions()["AAPL"].shares == 5


# --- cost basis: one test per way a position can change ---------------------


def test_increase_long_blends_cost_basis():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=5, price=110.0))
    position = broker.positions()["AAPL"]
    assert position.shares == 15
    assert position.cost_basis == pytest.approx((10 * 100.0 + 5 * 110.0) / 15)
    assert broker.realized_pnl() == pytest.approx(0.0)


def test_reduce_long_realizes_only_the_shares_sold():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    fill = broker.place_order(Order(ticker="AAPL", side="sell", quantity=4, price=110.0))
    position = broker.positions()["AAPL"]
    assert position.shares == 6
    assert position.cost_basis == pytest.approx(100.0)
    assert fill.realized_pnl == pytest.approx(4 * 10.0)
    assert broker.realized_pnl() == pytest.approx(40.0)


def test_close_long_exactly_realizes_and_clears_the_position():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    fill = broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=110.0))
    assert broker.positions() == {}
    assert fill.realized_pnl == pytest.approx(100.0)
    assert broker.realized_pnl() == pytest.approx(100.0)


def test_long_to_short_crossing_reopens_at_the_fill_price():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    fill = broker.place_order(Order(ticker="AAPL", side="sell", quantity=15, price=110.0))
    position = broker.positions()["AAPL"]
    assert position.shares == -5
    # The new short is priced off this fill, not off the long's basis.
    assert position.cost_basis == pytest.approx(110.0)
    # Only the 10 shares that actually closed realize anything.
    assert fill.realized_pnl == pytest.approx(10 * 10.0)
    assert broker.realized_pnl() == pytest.approx(100.0)


def test_increase_short_blends_cost_basis():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=100.0))
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=5, price=90.0))
    position = broker.positions()["AAPL"]
    assert position.shares == -15
    assert position.cost_basis == pytest.approx((10 * 100.0 + 5 * 90.0) / 15)
    assert broker.realized_pnl() == pytest.approx(0.0)


def test_reduce_short_realizes_the_fall_below_basis():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=100.0))
    fill = broker.place_order(Order(ticker="AAPL", side="buy", quantity=4, price=90.0))
    position = broker.positions()["AAPL"]
    assert position.shares == -6
    assert position.cost_basis == pytest.approx(100.0)
    assert fill.realized_pnl == pytest.approx(4 * 10.0)
    assert broker.realized_pnl() == pytest.approx(40.0)


def test_close_short_exactly_realizes_and_clears_the_position():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=100.0))
    fill = broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=90.0))
    assert broker.positions() == {}
    assert fill.realized_pnl == pytest.approx(100.0)
    assert broker.realized_pnl() == pytest.approx(100.0)


def test_short_to_long_crossing_reopens_at_the_fill_price():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=100.0))
    fill = broker.place_order(Order(ticker="AAPL", side="buy", quantity=15, price=90.0))
    position = broker.positions()["AAPL"]
    assert position.shares == 5
    assert position.cost_basis == pytest.approx(90.0)
    assert fill.realized_pnl == pytest.approx(10 * 10.0)
    assert broker.realized_pnl() == pytest.approx(100.0)


def test_realized_pnl_accumulates_across_reducing_trades():
    broker = SimBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=3, price=110.0))
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=3, price=120.0))
    assert broker.realized_pnl() == pytest.approx(3 * 10.0 + 3 * 20.0)
    assert broker.positions()["AAPL"].cost_basis == pytest.approx(100.0)


# --- commissions ------------------------------------------------------------


def test_commission_charged_on_both_sides():
    broker = SimBroker(cash=10_000.0, commission=Commission(per_trade=1.0, per_share=0.005))
    buy = broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    assert buy.commission == pytest.approx(1.0 + 0.005 * 10)
    assert broker.cash() == pytest.approx(10_000.0 - 1_000.0 - 1.05)

    sell = broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=100.0))
    assert sell.commission == pytest.approx(1.05)
    assert broker.cash() == pytest.approx(10_000.0 - 1_000.0 - 1.05 + 1_000.0 - 1.05)


def test_commission_does_not_move_cost_basis_or_realized_pnl():
    broker = SimBroker(cash=0.0, commission=Commission(per_trade=5.0, per_share=0.01))
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    # Basis is a price, not a price-plus-costs: the commission lands in cash.
    assert broker.positions()["AAPL"].cost_basis == pytest.approx(100.0)
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=10, price=110.0))
    assert broker.realized_pnl() == pytest.approx(100.0)


def test_commission_defaults_to_zero():
    broker = SimBroker(cash=10_000.0)
    fill = broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    assert fill.commission == 0.0
    assert broker.cash() == pytest.approx(9_000.0)


def test_same_orders_replay_to_the_same_book():
    orders = [
        Order(ticker="AAPL", side="buy", quantity=10, price=100.0),
        Order(ticker="AAPL", side="sell", quantity=15, price=110.0),
        Order(ticker="MSFT", side="sell", quantity=4, price=50.0),
        Order(ticker="AAPL", side="buy", quantity=8, price=105.0),
    ]
    books = []
    for _ in range(2):
        broker = SimBroker(cash=10_000.0, commission=Commission(per_trade=1.0, per_share=0.005))
        for order in orders:
            broker.place_order(order)
        books.append((broker.cash(), broker.realized_pnl(), broker.positions()))
    assert books[0] == books[1]
