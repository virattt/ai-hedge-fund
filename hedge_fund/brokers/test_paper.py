"""PaperBroker tests — open / fill / cancel and mark fills, no live venue."""

import pytest

from hedge_fund.brokers.models import Order
from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.brokers.protocol import Broker


def test_paper_broker_satisfies_the_protocol():
    broker = PaperBroker(cash=1_000.0)
    assert isinstance(broker, Broker)
    assert broker.venue == "paper"


def test_buy_updates_cash_and_position():
    broker = PaperBroker(cash=10_000.0)
    fill = broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    assert broker.cash() == pytest.approx(9_000.0)
    assert broker.positions()["AAPL"].shares == 10
    assert fill.quantity == 10
    assert fill.price == 100.0


def test_sell_updates_cash_and_position():
    broker = PaperBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=4, price=110.0))
    assert broker.positions()["AAPL"].shares == 6
    assert broker.cash() == pytest.approx(-1_000.0 + 440.0)


def test_position_removed_at_zero():
    broker = PaperBroker(cash=1_000.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=5, price=100.0))
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=5, price=100.0))
    assert broker.positions() == {}


def test_sell_past_zero_creates_short():
    broker = PaperBroker(cash=0.0)
    broker.place_order(Order(ticker="AAPL", side="sell", quantity=3, price=100.0))
    assert broker.positions()["AAPL"].shares == -3
    assert broker.cash() == pytest.approx(300.0)


def test_nonpositive_price_raises():
    broker = PaperBroker(cash=1_000.0)
    with pytest.raises(ValueError):
        broker.place_order(Order(ticker="AAPL", side="buy", quantity=1, price=0.0))


def test_positions_returns_a_copy():
    broker = PaperBroker(cash=1_000.0)
    broker.place_order(Order(ticker="AAPL", side="buy", quantity=5, price=100.0))
    broker.positions().clear()
    assert broker.positions()["AAPL"].shares == 5


def test_seeded_constructor_opens_the_given_book():
    seed = {"AAPL": 100, "MSFT": -25, "FLAT": 0}
    broker = PaperBroker(cash=90_000.0, positions=seed)
    assert broker.cash() == pytest.approx(90_000.0)
    assert {t: p.shares for t, p in broker.positions().items()} == {
        "AAPL": 100, "MSFT": -25,
    }
    seed["AAPL"] = 1
    assert broker.positions()["AAPL"].shares == 100


def test_open_then_fill_at_mark():
    broker = PaperBroker(cash=10_000.0)
    oid = broker.open_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    assert oid in broker.open_orders()
    assert broker.cash() == pytest.approx(10_000.0)
    assert broker.positions() == {}

    fill = broker.fill(oid)
    assert fill.price == 100.0
    assert fill.quantity == 10
    assert broker.cash() == pytest.approx(9_000.0)
    assert broker.positions()["AAPL"].shares == 10
    assert broker.open_orders() == {}


def test_open_then_cancel_leaves_the_book_untouched():
    broker = PaperBroker(cash=10_000.0)
    oid = broker.open_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    broker.cancel(oid)
    assert broker.cash() == pytest.approx(10_000.0)
    assert broker.positions() == {}
    assert broker.open_orders() == {}


def test_delayed_fill_uses_the_later_mark():
    broker = PaperBroker(cash=10_000.0)
    oid = broker.open_order(Order(ticker="AAPL", side="buy", quantity=10, price=100.0))
    fill = broker.fill(oid, price=105.0)
    assert fill.price == 105.0
    assert broker.cash() == pytest.approx(8_950.0)
    assert broker.positions()["AAPL"].shares == 10


def test_cannot_fill_or_cancel_a_filled_ticket():
    broker = PaperBroker(cash=10_000.0)
    oid = broker.open_order(Order(ticker="AAPL", side="buy", quantity=1, price=100.0))
    broker.fill(oid)
    with pytest.raises(ValueError, match="already filled"):
        broker.fill(oid)
    with pytest.raises(ValueError, match="already filled"):
        broker.cancel(oid)


def test_cannot_fill_or_cancel_a_cancelled_ticket():
    broker = PaperBroker(cash=10_000.0)
    oid = broker.open_order(Order(ticker="AAPL", side="buy", quantity=1, price=100.0))
    broker.cancel(oid)
    with pytest.raises(ValueError, match="already cancelled"):
        broker.fill(oid)
    with pytest.raises(ValueError, match="already cancelled"):
        broker.cancel(oid)


def test_unknown_ticket_raises():
    broker = PaperBroker(cash=1_000.0)
    with pytest.raises(ValueError, match="unknown order"):
        broker.fill("missing")
    with pytest.raises(ValueError, match="unknown order"):
        broker.cancel("missing")


def test_bad_delayed_mark_keeps_the_ticket_open():
    broker = PaperBroker(cash=10_000.0)
    oid = broker.open_order(Order(ticker="AAPL", side="buy", quantity=1, price=100.0))
    with pytest.raises(ValueError, match="must price"):
        broker.fill(oid, price=0.0)
    assert oid in broker.open_orders()
    fill = broker.fill(oid)
    assert fill.price == 100.0


def test_open_orders_returns_a_copy():
    broker = PaperBroker(cash=1_000.0)
    order = Order(ticker="AAPL", side="buy", quantity=2, price=50.0)
    oid = broker.open_order(order)
    broker.open_orders()[oid].quantity = 99
    order.quantity = 1
    assert broker.open_orders()[oid].quantity == 2


def test_place_order_is_open_and_fill_at_mark():
    broker = PaperBroker(cash=1_000.0)
    fill = broker.place_order(Order(ticker="MSFT", side="buy", quantity=2, price=100.0))
    assert fill.price == 100.0
    assert broker.open_orders() == {}
    assert broker.positions()["MSFT"].shares == 2
