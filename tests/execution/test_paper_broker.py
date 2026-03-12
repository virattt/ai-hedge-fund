"""Tests for src.execution.paper_broker."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.execution.models import Order, OrderSide, OrderType, AssetClass
from src.execution.paper_broker import PaperBroker


@pytest.fixture
def broker():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        b = PaperBroker(initial_cash=100_000, state_path=path, slippage_bps=10)
        yield b
    finally:
        Path(path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_paper_broker_buy_and_slippage(broker):
    await broker.connect()
    broker.set_last_price("AAPL", 150.0)
    order = Order(ticker="AAPL", side=OrderSide.BUY, quantity=10, order_type=OrderType.MARKET, asset_class=AssetClass.EQUITY)
    result = await broker.submit_order(order)
    assert result.status.value == "FILLED"
    assert result.filled_quantity == 10
    assert result.average_fill_price > 150.0
    await broker.disconnect()


@pytest.mark.asyncio
async def test_paper_broker_no_price_rejected(broker):
    await broker.connect()
    order = Order(ticker="UNKNOWN", side=OrderSide.BUY, quantity=10, order_type=OrderType.MARKET, asset_class=AssetClass.EQUITY)
    result = await broker.submit_order(order)
    assert result.status.value == "REJECTED"
    await broker.disconnect()
