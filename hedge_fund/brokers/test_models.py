"""Broker models — what an order and a fill serialize."""

from hedge_fund.brokers.models import Order


def test_an_order_serializes_its_liquidity_only_when_it_has_some():
    bare = Order(ticker="AAPL", side="buy", quantity=1, price=100.0)
    assert set(bare.model_dump()) == {"ticker", "side", "quantity", "price"}
    sized = Order(ticker="AAPL", side="buy", quantity=1, price=100.0, adv=1_000.0, volatility=0.02)
    assert sized.model_dump()["adv"] == 1_000.0 and sized.model_dump()["volatility"] == 0.02
    assert Order.model_validate_json(sized.model_dump_json()) == sized
