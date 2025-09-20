from src.backtesting.engine import BacktestEngine
from tests.backtesting.integration.mocks import MockConfigurableAgent

def test_long_only_strategy_buys_and_sells():
    """Test a strategy that buys shares, holds, then sells some shares to test realized gains/losses."""
    
    # Test parameters
    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"  
    end_date = "2024-03-08"    
    initial_capital = 100000.0  # $100k starting capital
    margin_requirement = 0.5   
    
    # Define the exact trading sequence we want to test
    decision_sequence = [
        # Day 1: Initial purchases
        {
            "AAPL": {"action": "buy", "quantity": 100},  # Buy 100 AAPL shares
            "MSFT": {"action": "buy", "quantity": 30},   # Buy 30 MSFT shares
            # TSLA will default to hold
        },
        # Day 2: Hold all positions (empty dict = hold all)
        {},
        # Day 3: Partial sell of AAPL
        {
            "AAPL": {"action": "sell", "quantity": 30},  # Sell 30 of 100 AAPL shares
            # MSFT and TSLA will default to hold
        },
        # Day 4+: Hold remaining positions (empty dict = hold all)
        {}
    ]
    
    # Create configurable agent with explicit trading plan
    agent = MockConfigurableAgent(decision_sequence, tickers)
    
    # Create and run backtest
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
    
    # Run the backtest
    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()
    
    # Get final portfolio state
    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]
    
    # Extract key values from our configuration for high-level verification
    initial_aapl_purchase = decision_sequence[0]["AAPL"]["quantity"]  # 100 
    aapl_sell_quantity = decision_sequence[2]["AAPL"]["quantity"]     # 30
    expected_final_aapl = initial_aapl_purchase - aapl_sell_quantity  # 70
    
    # Verify the final positions match our trading plan
    assert positions["AAPL"]["long"] == expected_final_aapl, f"AAPL position mismatch: expected {expected_final_aapl} shares, got {positions['AAPL']['long']}"
    assert positions["MSFT"]["long"] == 30, f"MSFT position mismatch: expected 30 shares, got {positions['MSFT']['long']}"
    assert positions["TSLA"]["long"] == 0, f"TSLA position mismatch: expected 0 shares, got {positions['TSLA']['long']}"
    
    # Verify the AAPL sale generated realized gains (proves sale happened)
    assert realized_gains["AAPL"]["long"] != 0.0, "AAPL should have realized gains from sale"
    assert realized_gains["MSFT"]["long"] == 0.0, "MSFT should have no realized gains (no sales)"
    
    # PORTFOLIO SUMMARY VERIFICATION: Focus on what matters most
    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]
    
    from src.backtesting.valuation import compute_portfolio_summary
    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics
    )
    
    # Core assertions: Portfolio summary calculations should be internally consistent
    actual_return_pct = portfolio_summary["return_pct"] 
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct, f"Return percentage should {expected_return_pct}"
    
    # Final portfolio value should be correct
    expected_total_value = final_cash + portfolio_summary["total_position_value"]
    assert final_portfolio_value == expected_total_value, f"Final portfolio value should be {expected_total_value}"


def test_long_only_strategy_full_liquidation_cycle():
    """Test a strategy that buys multiple positions, holds, then sells everything back to cash."""
    
    # Test parameters
    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"  
    end_date = "2024-03-08"    
    initial_capital = 100000.0  # $100k starting capital
    margin_requirement = 0.5   
    
    # Define the exact trading sequence we want to test
    decision_sequence = [
        # Day 1: Initial purchases - diversify across all tickers
        {
            "AAPL": {"action": "buy", "quantity": 50},   # Buy 50 AAPL shares
            "MSFT": {"action": "buy", "quantity": 25},   # Buy 25 MSFT shares
            "TSLA": {"action": "buy", "quantity": 30},   # Buy 30 TSLA shares
        },
        # Day 2: Hold all positions (empty dict = hold all)
        {},
        # Day 3: Begin liquidation - sell AAPL completely
        {
            "AAPL": {"action": "sell", "quantity": 50},  # Sell all AAPL
        },
        # Day 4: Complete liquidation - sell MSFT and TSLA completely
        {
            "MSFT": {"action": "sell", "quantity": 25},  # Sell all MSFT
            "TSLA": {"action": "sell", "quantity": 30},  # Sell all TSLA
        }
    ]
    
    # Create configurable agent with explicit trading plan
    agent = MockConfigurableAgent(decision_sequence, tickers)
    
    # Create and run backtest
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
    
    # Run the backtest
    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()
    
    # Get final portfolio state
    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]
    
    # Verify complete liquidation - should have no positions left
    assert positions["AAPL"]["long"] == 0, f"AAPL should be fully sold, got {positions['AAPL']['long']}"
    assert positions["MSFT"]["long"] == 0, f"MSFT should be fully sold, got {positions['MSFT']['long']}"
    assert positions["TSLA"]["long"] == 0, f"TSLA should be fully sold, got {positions['TSLA']['long']}"
    
    # Should have no short positions (long-only strategy)
    for ticker in tickers:
        assert positions[ticker]["short"] == 0, f"Expected no short position in {ticker}"
    
    # All tickers should have realized gains from complete liquidation
    assert realized_gains["AAPL"]["long"] != 0.0, "AAPL should have realized gains from sale"
    assert realized_gains["MSFT"]["long"] != 0.0, "MSFT should have realized gains from sale"
    assert realized_gains["TSLA"]["long"] != 0.0, "TSLA should have realized gains from sale"
    
    # Cost basis should be reset to zero after complete sales
    assert positions["AAPL"]["long_cost_basis"] == 0.0, "AAPL cost basis should be reset to 0"
    assert positions["MSFT"]["long_cost_basis"] == 0.0, "MSFT cost basis should be reset to 0"
    assert positions["TSLA"]["long_cost_basis"] == 0.0, "TSLA cost basis should be reset to 0"
    
    # PORTFOLIO SUMMARY VERIFICATION: Focus on what matters most
    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]
    
    from src.backtesting.valuation import compute_portfolio_summary
    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics
    )
    
    # Core assertions: Portfolio summary calculations should be internally consistent
    actual_return_pct = portfolio_summary["return_pct"] 
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct, f"Return percentage should be {expected_return_pct}"
    
    # After complete liquidation, portfolio should be mostly cash with no positions
    expected_total_position_value = 0.0  # No positions left
    assert portfolio_summary["total_position_value"] == expected_total_position_value, \
        f"Total position value should be 0 after liquidation, got {portfolio_summary['total_position_value']}"
    
    # Final portfolio value should equal cash balance (since no positions)
    assert abs(final_portfolio_value - final_cash) < 0.01, \
        f"Portfolio value should equal cash after liquidation: value={final_portfolio_value}, cash={final_cash}"


def test_long_only_strategy_portfolio_rebalancing():
    """Test a strategy that rebalances between stocks over time, validating complex position transitions."""
    
    # Test parameters
    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"  
    end_date = "2024-03-08"    
    initial_capital = 100000.0  # $100k starting capital
    margin_requirement = 0.5   
    
    # Define the exact trading sequence we want to test
    decision_sequence = [
        # Day 1: Initial allocation - focus on AAPL and MSFT
        {
            "AAPL": {"action": "buy", "quantity": 100},  # Buy 100 AAPL shares
            "MSFT": {"action": "buy", "quantity": 25},   # Buy 25 MSFT shares
            # TSLA remains empty (no position)
        },
        # Day 2: First rebalance - reduce AAPL, add TSLA
        {
            "AAPL": {"action": "sell", "quantity": 40},  # Sell 40 of 100 AAPL (60 remaining)
            "TSLA": {"action": "buy", "quantity": 30},   # Add 30 TSLA shares
            # MSFT holds at 25 shares
        },
        # Day 3: Hold all current positions
        {},
        # Day 4: Final rebalance - exit AAPL completely, increase MSFT
        {
            "AAPL": {"action": "sell", "quantity": 60},  # Sell remaining 60 AAPL
            "MSFT": {"action": "buy", "quantity": 15},   # Add 15 more MSFT (40 total)
            # TSLA holds at 30 shares
        }
    ]
    
    # Create configurable agent with explicit trading plan
    agent = MockConfigurableAgent(decision_sequence, tickers)
    
    # Create and run backtest
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
    
    # Run the backtest
    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()
    
    # Get final portfolio state
    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]
    
    # Extract expected values from our rebalancing configuration
    final_aapl_expected = 0      # Sold all: 100 initial - 40 - 60 = 0
    final_msft_expected = 40     # Accumulated: 25 initial + 15 = 40
    final_tsla_expected = 30     # Added: 0 initial + 30 = 30
    
    # Verify the final positions match our rebalancing plan
    assert positions["AAPL"]["long"] == final_aapl_expected, f"AAPL position mismatch: expected {final_aapl_expected} shares, got {positions['AAPL']['long']}"
    assert positions["MSFT"]["long"] == final_msft_expected, f"MSFT position mismatch: expected {final_msft_expected} shares, got {positions['MSFT']['long']}"
    assert positions["TSLA"]["long"] == final_tsla_expected, f"TSLA position mismatch: expected {final_tsla_expected} shares, got {positions['TSLA']['long']}"
    
    # Should have no short positions (long-only strategy)
    for ticker in tickers:
        assert positions[ticker]["short"] == 0, f"Expected no short position in {ticker}"
    
    # Verify realized gains from rebalancing activities
    assert realized_gains["AAPL"]["long"] != 0.0, "AAPL should have realized gains from partial and complete sales"
    assert realized_gains["MSFT"]["long"] == 0.0, "MSFT should have no realized gains (only bought, never sold)"
    assert realized_gains["TSLA"]["long"] == 0.0, "TSLA should have no realized gains (only bought, never sold)"
    
    # AAPL should have zero cost basis (completely sold)
    assert positions["AAPL"]["long_cost_basis"] == 0.0, "AAPL cost basis should be reset to 0 after complete sale"
    # MSFT and TSLA should have positive cost bases (still holding)
    assert positions["MSFT"]["long_cost_basis"] > 0.0, "MSFT should have positive cost basis (still holding)"
    assert positions["TSLA"]["long_cost_basis"] > 0.0, "TSLA should have positive cost basis (still holding)"
    
    # PORTFOLIO SUMMARY VERIFICATION: Focus on what matters most
    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]
    
    from src.backtesting.valuation import compute_portfolio_summary
    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics
    )
    
    # Core assertions: Portfolio summary calculations should be internally consistent
    actual_return_pct = portfolio_summary["return_pct"] 
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct, f"Return percentage should be {expected_return_pct}"
    
    # Portfolio should have mixed cash and positions after rebalancing
    expected_total_value = final_cash + portfolio_summary["total_position_value"]
    assert final_portfolio_value == expected_total_value, f"Final portfolio value should be {expected_total_value}"
    
    # Should have meaningful position values (not all cash, not zero cash)
    assert portfolio_summary["total_position_value"] > 0.0, "Should have position value after rebalancing"
    assert final_cash > 0.0, "Should have some cash remaining after rebalancing"
    
    # Verify that we successfully shifted from AAPL-heavy to MSFT+TSLA portfolio
    # Final positions should be worth a meaningful portion of the portfolio
    expected_min_position_value = initial_capital * 0.15  # At least 15% should be in positions after rebalancing
    assert portfolio_summary["total_position_value"] >= expected_min_position_value, \
        f"Total position value should be at least {expected_min_position_value}, got {portfolio_summary['total_position_value']}"


def test_long_only_strategy_multiple_entry_exit_cycles():
    """Test a strategy that performs multiple entry/exit cycles on the same ticker.

    Objective: validate realized gains aggregation across cycles, cost basis resets on full exits,
    and portfolio summary correctness at the end of the run.
    """
    
    # Test parameters
    tickers = ["AAPL", "MSFT", "TSLA"]
    start_date = "2024-03-01"  
    end_date = "2024-03-08"    
    initial_capital = 100000.0  # $100k starting capital
    margin_requirement = 0.5   
    
    # Multiple cycles on AAPL and MSFT within the available 4 business days (Mar 5-8)
    # Day 1: Buy AAPL 60, MSFT 20
    # Day 2: Sell AAPL 60, MSFT 20 (flat both)
    # Day 3: Buy AAPL 30, MSFT 10 (re-entry both)
    # Day 4: Sell AAPL 30, MSFT 10 (flat both again)
    decision_sequence = [
        {"AAPL": {"action": "buy", "quantity": 60}, "MSFT": {"action": "buy", "quantity": 20}},
        {"AAPL": {"action": "sell", "quantity": 60}, "MSFT": {"action": "sell", "quantity": 20}},
        {"AAPL": {"action": "buy", "quantity": 30}, "MSFT": {"action": "buy", "quantity": 10}},
        {"AAPL": {"action": "sell", "quantity": 30}, "MSFT": {"action": "sell", "quantity": 10}},
    ]
    
    # Create configurable agent with explicit trading plan
    agent = MockConfigurableAgent(decision_sequence, tickers)
    
    # Create and run backtest
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
    
    # Run the backtest
    performance_metrics = engine.run_backtest()
    portfolio_values = engine.get_portfolio_values()
    
    # Get final portfolio state
    final_portfolio = engine._portfolio.get_snapshot()
    positions = final_portfolio["positions"]
    realized_gains = final_portfolio["realized_gains"]
    
    # Verify final positions are flat after multiple cycles
    assert positions["AAPL"]["long"] == 0, f"AAPL should be fully sold after cycles, got {positions['AAPL']['long']}"
    assert positions["MSFT"]["long"] == 0, f"MSFT should be fully sold after cycles, got {positions['MSFT']['long']}"
    assert positions["TSLA"]["long"] == 0, f"TSLA should be 0 shares (never traded), got {positions['TSLA']['long']}"
    
    # Should have no short positions (long-only strategy)
    for ticker in tickers:
        assert positions[ticker]["short"] == 0, f"Expected no short position in {ticker}"
    
    # Realized gains should be non-zero for AAPL and MSFT due to two completed round trips
    assert realized_gains["AAPL"]["long"] != 0.0, "AAPL should have realized gains/losses from multiple cycles"
    assert realized_gains["MSFT"]["long"] != 0.0, "MSFT should have realized gains/losses from multiple cycles"
    assert realized_gains["TSLA"]["long"] == 0.0, "TSLA should have no realized gains (not traded)"
    
    # Cost basis should be reset to zero for AAPL and MSFT after final full exit
    assert positions["AAPL"]["long_cost_basis"] == 0.0, "AAPL cost basis should reset to 0 after full exit"
    assert positions["MSFT"]["long_cost_basis"] == 0.0, "MSFT cost basis should reset to 0 after full exit"
    
    # PORTFOLIO SUMMARY VERIFICATION
    final_portfolio_value = portfolio_values[-1]["Portfolio Value"]
    final_cash = final_portfolio["cash"]
    
    from src.backtesting.valuation import compute_portfolio_summary
    portfolio_summary = compute_portfolio_summary(
        portfolio=engine._portfolio,
        total_value=final_portfolio_value,
        initial_value=initial_capital,
        performance_metrics=performance_metrics
    )
    
    # Core assertions: Portfolio summary calculations should be internally consistent
    actual_return_pct = portfolio_summary["return_pct"] 
    expected_return_pct = (final_portfolio_value / initial_capital - 1.0) * 100.0
    assert actual_return_pct == expected_return_pct, f"Return percentage should be {expected_return_pct}"
    
    # After final liquidation, no positions should remain
    assert portfolio_summary["total_position_value"] == 0.0, \
        f"Total position value should be 0 after final liquidation, got {portfolio_summary['total_position_value']}"
    assert abs(final_portfolio_value - final_cash) < 0.01, \
        f"Portfolio value should equal cash after final liquidation: value={final_portfolio_value}, cash={final_cash}"
