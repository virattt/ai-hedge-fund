from src.backtesting.valuation import calculate_portfolio_value, compute_exposures, compute_portfolio_summary


def test_calculate_portfolio_value(portfolio, prices):
    # Long 10 AAPL @100 and short 5 MSFT @200
    portfolio.apply_long_buy("AAPL", 10, 100.0)
    portfolio.apply_short_open("MSFT", 5, 200.0)

    value = calculate_portfolio_value(portfolio, prices)
    # cash after trades
    snap = portfolio.get_snapshot()
    expected = snap["cash"] + 10 * 100.0 - 5 * 200.0
    assert value == expected


def test_compute_exposures(portfolio, prices):
    portfolio.apply_long_buy("AAPL", 10, 100.0)
    portfolio.apply_short_open("MSFT", 5, 200.0)

    exp = compute_exposures(portfolio, prices)
    assert exp["Long Exposure"] == 1000.0
    assert exp["Short Exposure"] == 1000.0
    assert exp["Gross Exposure"] == 2000.0
    assert exp["Net Exposure"] == 0.0
    assert exp["Long/Short Ratio"] == 1.0


def test_compute_exposures_with_no_shorts_ratio_inf(portfolio, prices):
    portfolio.apply_long_buy("AAPL", 1, 100.0)
    exp = compute_exposures(portfolio, prices)
    assert exp["Short Exposure"] == 0.0
    assert exp["Long/Short Ratio"] == float("inf")


def test_compute_portfolio_summary(portfolio, prices):
    portfolio.apply_long_buy("AAPL", 10, 100.0)
    total_value = calculate_portfolio_value(portfolio, prices)
    summary = compute_portfolio_summary(
        portfolio=portfolio,
        total_value=total_value,
        initial_value=100_000.0,
        performance_metrics={"sharpe_ratio": 1.0, "sortino_ratio": 2.0, "max_drawdown": -5.0},
    )
    assert summary["cash_balance"] == 99_000.0
    assert summary["total_position_value"] == 1_000.0
    assert summary["total_value"] == total_value
    assert summary["return_pct"] == 0.0
    assert summary["sharpe_ratio"] == 1.0

