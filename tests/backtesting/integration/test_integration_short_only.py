from src.backtesting.engine import BacktestEngine
from tests.backtesting.integration.mocks import MockConfigurableAgent


def test_short_only_strategy_shorts_and_covers():
    """Short, hold, then partial cover. Validate positions, realized gains, and summary consistency."""

    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"
    end_date = "2024-03-08"
    initial_capital = 100000.0
    margin_requirement = 0.5

    # Day1: open shorts; Day2: hold; Day3: partial cover AAPL; Day4: hold
    decision_sequence = [
        {
            "AAPL": {"action": "short", "quantity": 100},
            "MSFT": {"action": "short", "quantity": 30},
        },
        {},
        {
            "AAPL": {"action": "cover", "quantity": 30},
        },
        {},
    ]

    agent = MockConfigurableAgent(decision_sequence, tickers)

    engine = BacktestEngine(
        agent=agent,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        model_name="test-model",
        model_provider="test-provider",
        selected_analysts=None,
        initial_margin_requirement=margin_requirement,
    )

    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()

    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]

    # Expected: AAPL 70 short remaining, MSFT 30 short, TSLA 0
    assert positions["AAPL"]["short"] == 70
    assert positions["MSFT"]["short"] == 30
    assert positions["TSLA"]["short"] == 0
    # No long positions in a short-only plan
    for t in tickers:
        assert positions[t]["long"] == 0

    # AAPL partial cover should realize non-zero gains/losses; MSFT none; TSLA none
    assert realized_gains["AAPL"]["short"] != 0.0
    assert realized_gains["MSFT"]["short"] == 0.0
    assert realized_gains["TSLA"]["short"] == 0.0

    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]

    from src.backtesting.valuation import compute_portfolio_summary

    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics,
    )

    actual_return_pct = portfolio_summary["return_pct"]
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct

    expected_total_value = final_cash + portfolio_summary["total_position_value"]
    assert final_portfolio_value == expected_total_value


def test_short_only_strategy_full_cover_cycle():
    """Open shorts, then fully cover all to return to flat and mostly cash."""

    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"
    end_date = "2024-03-08"
    initial_capital = 100000.0
    margin_requirement = 0.5

    decision_sequence = [
        {
            "AAPL": {"action": "short", "quantity": 50},
            "MSFT": {"action": "short", "quantity": 25},
            "TSLA": {"action": "short", "quantity": 30},
        },
        {},
        {
            "AAPL": {"action": "cover", "quantity": 50},
        },
        {
            "MSFT": {"action": "cover", "quantity": 25},
            "TSLA": {"action": "cover", "quantity": 30},
        },
    ]

    agent = MockConfigurableAgent(decision_sequence, tickers)

    engine = BacktestEngine(
        agent=agent,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        model_name="test-model",
        model_provider="test-provider",
        selected_analysts=None,
        initial_margin_requirement=margin_requirement,
    )

    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()

    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]

    # After full cover, all shorts 0
    assert positions["AAPL"]["short"] == 0
    assert positions["MSFT"]["short"] == 0
    assert positions["TSLA"]["short"] == 0
    # No longs
    for t in tickers:
        assert positions[t]["long"] == 0

    # All tickers should have realized short-side PnL
    assert realized_gains["AAPL"]["short"] != 0.0
    assert realized_gains["MSFT"]["short"] != 0.0
    assert realized_gains["TSLA"]["short"] != 0.0

    # Cost basis reset after flat
    assert positions["AAPL"]["short_cost_basis"] == 0.0
    assert positions["MSFT"]["short_cost_basis"] == 0.0
    assert positions["TSLA"]["short_cost_basis"] == 0.0

    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]

    from src.backtesting.valuation import compute_portfolio_summary

    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics,
    )

    actual_return_pct = portfolio_summary["return_pct"]
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct

    # No positions -> position value 0; portfolio value ~ cash
    assert portfolio_summary["total_position_value"] == 0.0
    assert abs(final_portfolio_value - final_cash) < 0.01


def test_short_only_strategy_multiple_short_cover_cycles():
    """Perform two complete short-cover cycles to test realized gains aggregation and resets."""

    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"
    end_date = "2024-03-08"
    initial_capital = 100000.0
    margin_requirement = 0.5

    decision_sequence = [
        {"AAPL": {"action": "short", "quantity": 60}, "MSFT": {"action": "short", "quantity": 20}},
        {"AAPL": {"action": "cover", "quantity": 60}, "MSFT": {"action": "cover", "quantity": 20}},
        {"AAPL": {"action": "short", "quantity": 30}, "MSFT": {"action": "short", "quantity": 10}},
        {"AAPL": {"action": "cover", "quantity": 30}, "MSFT": {"action": "cover", "quantity": 10}},
    ]

    agent = MockConfigurableAgent(decision_sequence, tickers)

    engine = BacktestEngine(
        agent=agent,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        model_name="test-model",
        model_provider="test-provider",
        selected_analysts=None,
        initial_margin_requirement=margin_requirement,
    )

    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()

    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]

    # Flat after cycles
    assert positions["AAPL"]["short"] == 0
    assert positions["MSFT"]["short"] == 0
    assert positions["TSLA"]["short"] == 0
    for t in tickers:
        assert positions[t]["long"] == 0

    # Realized gains should be non-zero for cycled names
    assert realized_gains["AAPL"]["short"] != 0.0
    assert realized_gains["MSFT"]["short"] != 0.0
    assert realized_gains["TSLA"]["short"] == 0.0

    # Cost basis resets after final flat
    assert positions["AAPL"]["short_cost_basis"] == 0.0
    assert positions["MSFT"]["short_cost_basis"] == 0.0

    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]

    from src.backtesting.valuation import compute_portfolio_summary

    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics,
    )

    actual_return_pct = portfolio_summary["return_pct"]
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct

    assert portfolio_summary["total_position_value"] == 0.0
    assert abs(final_portfolio_value - final_cash) < 0.01



def test_short_only_strategy_portfolio_rebalancing():
    """Rebalance across shorts: reduce AAPL short, add TSLA, then close AAPL and add to MSFT."""

    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"
    end_date = "2024-03-08"
    initial_capital = 100000.0
    margin_requirement = 0.5

    decision_sequence = [
        # Day 1: Initial shorts - focus on AAPL and MSFT
        {
            "AAPL": {"action": "short", "quantity": 100},
            "MSFT": {"action": "short", "quantity": 25},
        },
        # Day 2: First rebalance - reduce AAPL, add TSLA
        {
            "AAPL": {"action": "cover", "quantity": 40},  # 60 short remaining
            "TSLA": {"action": "short", "quantity": 30},   # add new short
        },
        # Day 3: Hold
        {},
        # Day 4: Final rebalance - close AAPL short, increase MSFT short
        {
            "AAPL": {"action": "cover", "quantity": 60},   # close AAPL
            "MSFT": {"action": "short", "quantity": 15},   # MSFT 40 total
        },
    ]

    agent = MockConfigurableAgent(decision_sequence, tickers)

    engine = BacktestEngine(
        agent=agent,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        model_name="test-model",
        model_provider="test-provider",
        selected_analysts=None,
        initial_margin_requirement=margin_requirement,
    )

    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()

    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]

    # Final expected shorts
    assert positions["AAPL"]["short"] == 0
    assert positions["MSFT"]["short"] == 40
    assert positions["TSLA"]["short"] == 30
    # No longs
    for t in tickers:
        assert positions[t]["long"] == 0

    # Realized gains only for AAPL (covered), none for MSFT/TSLA (still open)
    assert realized_gains["AAPL"]["short"] != 0.0
    assert realized_gains["MSFT"]["short"] == 0.0
    assert realized_gains["TSLA"]["short"] == 0.0

    # Cost basis reset for AAPL, positive for open shorts
    assert positions["AAPL"]["short_cost_basis"] == 0.0
    assert positions["MSFT"]["short_cost_basis"] > 0.0
    assert positions["TSLA"]["short_cost_basis"] > 0.0

    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]

    from src.backtesting.valuation import compute_portfolio_summary

    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics,
    )

    # Summary math consistency
    actual_return_pct = portfolio_summary["return_pct"]
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct
    expected_total_value = final_cash + portfolio_summary["total_position_value"]
    assert final_portfolio_value == expected_total_value
    # Still have open shorts, so position value magnitude should be > 0
    assert abs(portfolio_summary["total_position_value"]) > 0.0


def test_short_only_strategy_dollar_cost_averaging_on_short():
    """Add to an existing short (averaging entry), then partially cover and validate cost basis and PnL."""

    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"
    end_date = "2024-03-08"
    initial_capital = 100000.0
    margin_requirement = 0.5

    decision_sequence = [
        # Day 1: initial short
        {"AAPL": {"action": "short", "quantity": 50}},
        # Day 2: add to short at a new price (tests weighted avg cost)
        {"AAPL": {"action": "short", "quantity": 30}},
        # Day 3: hold
        {},
        # Day 4: partial cover
        {"AAPL": {"action": "cover", "quantity": 40}},
    ]

    agent = MockConfigurableAgent(decision_sequence, tickers)

    engine = BacktestEngine(
        agent=agent,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        model_name="test-model",
        model_provider="test-provider",
        selected_analysts=None,
        initial_margin_requirement=margin_requirement,
    )

    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()

    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]

    # 80 short opened, 40 covered -> 40 remaining
    assert positions["AAPL"]["short"] == 40
    assert positions["MSFT"]["short"] == 0
    assert positions["TSLA"]["short"] == 0
    for t in tickers:
        assert positions[t]["long"] == 0

    # Weighted short_cost_basis should be positive (non-zero) while position remains
    assert positions["AAPL"]["short_cost_basis"] > 0.0

    # Partial cover should realize PnL
    assert realized_gains["AAPL"]["short"] != 0.0

    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]

    from src.backtesting.valuation import compute_portfolio_summary

    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics,
    )

    actual_return_pct = portfolio_summary["return_pct"]
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct
    expected_total_value = final_cash + portfolio_summary["total_position_value"]
    assert final_portfolio_value == expected_total_value
    # Open short remains -> non-zero position value magnitude
    assert abs(portfolio_summary["total_position_value"]) > 0.0

