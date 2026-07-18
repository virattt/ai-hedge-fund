from app.backend.services.backtest_service import BacktestService
from app.backend.services.portfolio import create_portfolio


def test_short_open_preserves_web_backtest_equity_and_buying_power() -> None:
    service = BacktestService(
        graph=None,
        portfolio=create_portfolio(1_000.0, 0.5, ["AAPL"]),
        tickers=["AAPL"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        initial_capital=1_000.0,
    )

    assert service.execute_trade("AAPL", "short", 10, 100.0) == 10
    assert service.calculate_portfolio_value({"AAPL": 100.0}) == 1_000.0
    assert service.calculate_portfolio_value({"AAPL": 110.0}) == 900.0
    assert service.execute_trade("AAPL", "short", 30, 100.0) == 10
    assert service._available_cash() == 0.0
