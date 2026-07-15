from integrations.alpaca.executor import decisions_to_orders, validate_order
from integrations.alpaca.config import AlpacaConfig
from integrations.alpaca.portfolio_sync import merge_tickers, positions_to_portfolio
from integrations.broker.models import AccountSnapshot, Position, TradeOrder
from integrations.broker.noop import NoOpBroker


def test_decisions_to_orders():
    decisions = {
        "AAPL": {"action": "buy", "quantity": 10, "reasoning": "bullish"},
        "MSFT": {"action": "hold", "quantity": 0, "reasoning": "neutral"},
    }
    orders = decisions_to_orders(decisions)
    assert len(orders) == 2
    assert orders[0].ticker == "AAPL"
    assert orders[0].action == "buy"
    assert orders[0].quantity == 10


def test_noop_broker_dry_run():
    broker = NoOpBroker(cash=50_000)
    result = broker.submit_order(TradeOrder(ticker="AAPL", action="buy", quantity=5, reason="test"))
    assert result.dry_run is True
    assert result.submitted is False


def test_positions_to_portfolio():
    account = AccountSnapshot(cash=10_000, equity=15_000, buying_power=10_000, portfolio_value=15_000)
    positions = [
        Position(ticker="AAPL", quantity=10, avg_entry_price=150.0, market_value=1500.0, side="long"),
    ]
    portfolio = positions_to_portfolio(
        account=account,
        positions=positions,
        tickers=["AAPL", "MSFT"],
        margin_requirement=0.5,
    )
    assert portfolio["cash"] == 10_000
    assert portfolio["positions"]["AAPL"]["long"] == 10
    assert portfolio["positions"]["MSFT"]["long"] == 0


def test_merge_tickers_includes_positions():
    positions = [Position(ticker="NVDA", quantity=5, side="long")]
    tickers = merge_tickers(["AAPL"], positions)
    assert tickers == ["AAPL", "NVDA"]


def test_validate_order_kill_switch():
    config = AlpacaConfig(
        api_key="k",
        secret_key="s",
        paper=True,
        live_trading_enabled=True,
        kill_switch=True,
        max_order_notional=5000,
        allowed_tickers=None,
        margin_requirement=0.5,
    )
    order = TradeOrder(ticker="AAPL", action="buy", quantity=1)
    assert validate_order(order, config, 100.0) == "Kill switch is active."
