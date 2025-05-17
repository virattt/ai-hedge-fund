#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Portfolio Week Simulation Example

This example simulates a portfolio's performance over a week (5 trading days)
with different market conditions each day. It demonstrates how the portfolio metrics
change dynamically based on market movements.
"""

import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json

# Add the src directory to the path so we can import modules as they expect
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'src'))

# Import with the structure expected by the project modules
from new_graph.state import AgentState, EnhancedAgentState
from new_models.portfolio import Portfolio, Strategy, Leg, Greeks, RiskProfile, MarketConditions, OptionPal

# Create a custom portfolio metrics calculation function
def calculate_portfolio_metrics(enhanced_state):
    """
    Calculate portfolio metrics using the new_graph.state model.
    This is a simplified version of the portfolio_metrics_agent that works with our data model.
    """
    # Access data using dot notation as per the user's preference
    portfolio = enhanced_state.data.portfolio
    market_conditions = enhanced_state.data.market_conditions
    
    # Calculate portfolio-level metrics
    
    # 1. Update P&L based on market movements
    # For simplicity, we'll use a basic model where P&L is affected by delta and gamma exposure
    spx = market_conditions.spx
    vix = market_conditions.vix
    
    # Calculate expected daily move based on VIX
    # VIX represents expected annualized volatility, so we need to convert to daily
    # Formula: Expected Daily Move = SPX * VIX * sqrt(1/252) / 100
    expected_daily_move = spx * vix * (1 / np.sqrt(252)) / 100
    market_conditions.expected_daily_move = expected_daily_move
    
    # Initialize portfolio-level Greeks
    portfolio_delta = 0
    portfolio_gamma = 0
    portfolio_theta = 0
    portfolio_vega = 0
    
    # Update strategy-level metrics for each strategy
    for i in range(len(portfolio.strategies)):
        strategy = portfolio.strategy(i)
        
        # Calculate total strategy Greeks by summing up leg Greeks
        strategy_delta = 0
        strategy_gamma = 0
        strategy_theta = 0
        strategy_vega = 0
        
        # Sum up the Greeks from all legs
        for leg in strategy.legs:
            multiplier = leg.multiplier
            # For options, apply the position size (put/call)
            if leg.type == "option":
                position = leg.put if hasattr(leg, "put") and leg.put != 0 else leg.call
                strategy_delta += leg.greeks.delta * multiplier * position
                strategy_gamma += leg.greeks.gamma * multiplier * position
                strategy_theta += leg.greeks.theta * multiplier * position
                strategy_vega += leg.greeks.vega * multiplier * position
        
        # Calculate strategy P&L components
        strategy_delta_pnl = strategy_delta * (expected_daily_move / 100)
        strategy_gamma_pnl = strategy_gamma * (expected_daily_move / 100) ** 2
        strategy_theta_pnl = strategy_theta / 252  # Daily theta
        strategy_vega_pnl = strategy_vega * (market_conditions.vix_1d / 100)
        
        # Update strategy P&L
        strategy.pnl = strategy_delta_pnl + strategy_gamma_pnl + strategy_theta_pnl + strategy_vega_pnl
        
        # Update risk profile metrics
        strategy.risk_profile.expected_delta_move = strategy_delta * (expected_daily_move / 100)
        strategy.risk_profile.expected_convexity_move = strategy_gamma * (expected_daily_move / 100) ** 2
        
        # Update marginal contribution to risk
        strategy.risk_profile.marginal_contribution_to_risk = strategy.pnl / portfolio.pnl if portfolio.pnl != 0 else 0
        
        # Accumulate portfolio-level Greeks
        portfolio_delta += strategy_delta
        portfolio_gamma += strategy_gamma
        portfolio_theta += strategy_theta
        portfolio_vega += strategy_vega
    
    # Update portfolio-level metrics
    portfolio.total_beta_weighted_delta = portfolio_delta
    portfolio.total_beta_weighted_gamma = portfolio_gamma
    portfolio.theta = portfolio_theta
    
    # Print debug information about gamma values
    print(f"DEBUG - Portfolio gamma: {portfolio_gamma}, Expected move: {expected_daily_move}")
    
    # Update portfolio expected daily move values
    portfolio.expected_daily_move.directional_exposure = portfolio_delta * (expected_daily_move / 100)
    portfolio.expected_daily_move.convexity_exposure = portfolio_gamma * (expected_daily_move / 100) ** 2
    portfolio.expected_daily_move.volatility_exposure = portfolio_vega * (market_conditions.vix_1d / 100)
    
    # Calculate P&L components
    delta_pnl = portfolio.expected_daily_move.directional_exposure
    gamma_pnl = portfolio.expected_daily_move.convexity_exposure
    theta_pnl = portfolio.theta / 252  # Daily theta
    vega_pnl = portfolio.expected_daily_move.volatility_exposure
    
    # Update portfolio value and P&L
    previous_value = portfolio.net_liquidation_value
    portfolio.pnl = delta_pnl + gamma_pnl + theta_pnl + vega_pnl
    portfolio.net_liquidation_value = previous_value + portfolio.pnl
    portfolio.pnl_percent = (portfolio.pnl / previous_value) * 100 if previous_value > 0 else 0
    
    return enhanced_state

# Create a function to use the portfolio metrics calculations directly
def apply_portfolio_metrics(enhanced_state):
    """
    Apply the portfolio metrics calculations using the custom function.
    This works directly with EnhancedAgentState objects.
    """
    # Step 1: Calculate market conditions
    # For simplicity, we'll assume market conditions are already set
    
    # Step 2: Calculate portfolio-level metrics
    enhanced_state = calculate_portfolio_metrics(enhanced_state)
    
    return enhanced_state

# Create a function to simulate market movements
def simulate_market_day(previous_conditions, day_number, scenario="normal"):
    """
    Simulate market movements for a day based on the scenario.
    
    Args:
        previous_conditions: MarketConditions from the previous day
        day_number: The day number in the simulation (1-5)
        scenario: Market scenario for the day (normal, volatile, crash, rally, recovery)
        
    Returns:
        MarketConditions: Updated market conditions
    """
    # Extract previous values
    prev_spx = previous_conditions.spx
    prev_vix = previous_conditions.vix
    prev_vvix = previous_conditions.vvix
    
    # Define scenario parameters
    scenarios = {
        "normal": {
            "spx_change_pct": lambda: np.random.normal(0.05, 0.5),  # Small random movement
            "vix_change": lambda: np.random.normal(0, 0.5),  # Small random VIX change
            "vvix_change": lambda: np.random.normal(0, 2.0)  # Small random VVIX change
        },
        "volatile": {
            "spx_change_pct": lambda: np.random.normal(-0.2, 1.2),  # Larger random movement
            "vix_change": lambda: np.random.normal(3.0, 1.5),  # VIX increases
            "vvix_change": lambda: np.random.normal(10.0, 5.0)  # VVIX increases significantly
        },
        "crash": {
            "spx_change_pct": lambda: np.random.normal(-2.5, 1.0),  # Significant drop
            "vix_change": lambda: np.random.normal(8.0, 2.0),  # VIX spikes
            "vvix_change": lambda: np.random.normal(20.0, 8.0)  # VVIX spikes
        },
        "rally": {
            "spx_change_pct": lambda: np.random.normal(1.8, 0.8),  # Significant rise
            "vix_change": lambda: np.random.normal(-3.0, 1.5),  # VIX decreases
            "vvix_change": lambda: np.random.normal(-8.0, 4.0)  # VVIX decreases
        },
        "recovery": {
            "spx_change_pct": lambda: np.random.normal(0.8, 0.6),  # Moderate rise
            "vix_change": lambda: np.random.normal(-1.5, 1.0),  # VIX continues to decrease
            "vvix_change": lambda: np.random.normal(-5.0, 3.0)  # VVIX continues to decrease
        }
    }
    
    # Get scenario parameters
    params = scenarios.get(scenario.lower(), scenarios["normal"])
    
    # Calculate new values
    spx_change_pct = params["spx_change_pct"]()
    vix_change = params["vix_change"]()
    vvix_change = params["vvix_change"]()
    
    # Update market values
    new_spx = prev_spx * (1 + spx_change_pct / 100)
    new_vix = max(9.0, prev_vix + vix_change)  # VIX floor at 9
    new_vvix = max(50.0, prev_vvix + vvix_change)  # VVIX floor at 50
    
    # Calculate expected daily move (approximately 1 market day move in points)
    expected_daily_move = new_spx * (new_vix / 100) / np.sqrt(252)
    
    # Calculate 1-day expected move in VIX
    vix_1d = new_vix * (new_vvix / 100) / np.sqrt(252)
    
    # Create and return a MarketConditions object
    return MarketConditions(
        spx=new_spx,
        vix=new_vix,
        vvix=new_vvix,
        vix_1d=vix_1d,
        expected_daily_move=expected_daily_move
    )

# Function to create a sample portfolio
def create_sample_portfolio():
    """
    Create a sample portfolio with different strategy types.
    
    Returns:
        Portfolio: A sample portfolio with strategies
    """
    portfolio = Portfolio(
        cash=100000.0,
        net_liquidation_value=100000.0,
        margin_used=0.0,
        max_margin=0.0,
        pnl=0.0,
        pnl_percent=0.0
    )
    
    # Create an SPX Iron Condor strategy
    spx_strategy = Strategy(
        ticker="SPX",
        asset_class="equity",
        description="SPX Iron Condor - Iron Condor Strategy",
        beta=1.0,
        risk_profile=RiskProfile(
            risk_category="defined",
            margin=0.0,
            CVaR=0.0
        ),
        premium=400.0,  # Net credit received (500 + 500 - 300 - 300)
        price=4700.0,   # Current price of SPX
        ivr=30.0,       # Current IVR of SPX
        number_of_contracts=1,
        number_of_legs=4
    )
    
    # Current date for expiry calculations
    current_date = datetime.now()
    expiry_date = (current_date + timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Add option legs for the iron condor
    # Short call spread
    short_call = Leg(
        id="spx_short_call",
        description="SPX Short Call",
        type="option",
        cost_basis=-500.0,  # Credit received
        multiplier=100,
        put=0,
        call=-1,  # Short call
        strike=4800,
        expiry=expiry_date,
        greeks=Greeks(
            delta=-0.15,
            gamma=-0.002,
            theta=0.5,
            vega=-0.2
        )
    )
    
    long_call = Leg(
        id="spx_long_call",
        description="SPX Long Call",
        type="option",
        cost_basis=300.0,  # Debit paid
        multiplier=100,
        put=0,
        call=1,  # Long call
        strike=4850,
        expiry=expiry_date,
        greeks=Greeks(
            delta=0.1,
            gamma=0.001,
            theta=-0.3,
            vega=0.15
        )
    )
    
    # Short put spread
    short_put = Leg(
        id="spx_short_put",
        description="SPX Short Put",
        type="option",
        cost_basis=-500.0,  # Credit received
        multiplier=100,
        put=-1,  # Short put
        call=0,
        strike=4600,
        expiry=expiry_date,
        greeks=Greeks(
            delta=-0.15,
            gamma=-0.002,
            theta=0.5,
            vega=-0.2
        )
    )
    
    long_put = Leg(
        id="spx_long_put",
        description="SPX Long Put",
        type="option",
        cost_basis=300.0,  # Debit paid
        multiplier=100,
        put=1,  # Long put
        call=0,
        strike=4550,
        expiry=expiry_date,
        greeks=Greeks(
            delta=0.1,
            gamma=0.001,
            theta=-0.3,
            vega=0.15
        )
    )
    
    # Add legs to the strategy
    spx_strategy.legs = [short_call, long_call, short_put, long_put]
    
    # Create a QQQ Covered Call strategy
    qqq_strategy = Strategy(
        ticker="QQQ",
        asset_class="equity",
        description="QQQ Covered Call - Long Stock with Short Call",
        beta=1.2,
        risk_profile=RiskProfile(
            risk_category="defined",
            margin=0.0,
            CVaR=0.0
        ),
        premium=-39700.0,  # Net debit paid (40000 - 300)
        price=400.0,       # Current price of QQQ
        ivr=25.0,          # Current IVR of QQQ
        number_of_contracts=1,
        number_of_legs=2
    )
    
    # Stock leg
    stock_leg = Leg(
        id="qqq_stock",
        description="QQQ Stock",
        type="stock",
        cost_basis=40000.0,  # 100 shares at $400 each
        multiplier=1,
        greeks=Greeks(
            delta=1.0,
            gamma=0.0,
            theta=0.0,
            vega=0.0
        )
    )
    
    # Call option leg
    call_leg = Leg(
        id="qqq_call",
        description="QQQ Covered Call",
        type="option",
        cost_basis=-300.0,  # Credit received
        multiplier=100,
        put=0,
        call=-1,  # Short call
        strike=410,
        expiry=expiry_date,
        greeks=Greeks(
            delta=-0.3,
            gamma=-0.01,
            theta=0.7,
            vega=-0.3
        )
    )
    
    # Add legs to the strategy
    qqq_strategy.legs = [stock_leg, call_leg]
    
    # Add strategies to the portfolio
    portfolio.strategies = [spx_strategy, qqq_strategy]
    
    return portfolio

# Main simulation function
def run_week_simulation():
    """
    Run a simulation of portfolio performance over a week.
    """
    # Create initial state with proper structure based on AgentState class
    state = AgentState(
        messages=[],
        data={},
        metadata={}
    )
    
    # Create enhanced state that uses the proper OptionPal model
    enhanced_state = EnhancedAgentState(state)
    
    # Set up the portfolio and market conditions using the proper model structure
    enhanced_state.data.portfolio = create_sample_portfolio()
    enhanced_state.data.market_conditions = MarketConditions(
        spx=4700.0,
        vix=16.0,
        vvix=90.0,
        vix_1d=0.0,
        expected_daily_move=0.0
    )
    enhanced_state.data.date = datetime.now().strftime("%Y-%m-%d")
    
    # Define market scenarios for each day
    scenarios = [
        "normal",    # Day 1: Normal market
        "volatile",  # Day 2: Increased volatility
        "crash",     # Day 3: Market crash
        "rally",     # Day 4: Market rally
        "recovery"   # Day 5: Market recovery
    ]
    
    # Store results for plotting
    results = {
        "dates": [],
        "spx_values": [],
        "vix_values": [],
        "portfolio_values": [],
        "delta_exposures": [],
        "gamma_exposures": [],
        "theta_exposures": [],
        "vega_exposures": []
    }
    
    # Run simulation for each day
    print("Starting portfolio week simulation...")
    
    for day, scenario in enumerate(scenarios):
        day_date = (datetime.now() + timedelta(days=day)).strftime("%Y-%m-%d")
        print(f"\nDay {day+1} ({day_date}) - {scenario.capitalize()} Market:")
        
        # Update the date in the state
        enhanced_state.data.date = day_date
        
        # Simulate market movement for the day
        if day == 0:
            # First day uses initial conditions
            market_conditions = enhanced_state.data.market_conditions
        else:
            # Subsequent days simulate movement based on previous day
            market_conditions = simulate_market_day(
                previous_conditions=enhanced_state.data.market_conditions,
                day_number=day,
                scenario=scenario
            )
            # Update market conditions in the state
            enhanced_state.data.market_conditions = market_conditions
        
        # Run the portfolio metrics calculations
        enhanced_state = apply_portfolio_metrics(enhanced_state)
        
        # Store results for this day
        results["dates"].append(day_date)
        results["spx_values"].append(enhanced_state.data.market_conditions.spx)
        results["vix_values"].append(enhanced_state.data.market_conditions.vix)
        results["portfolio_values"].append(enhanced_state.data.portfolio.net_liquidation_value)
        results["delta_exposures"].append(enhanced_state.data.portfolio.expected_daily_move.directional_exposure)
        results["gamma_exposures"].append(enhanced_state.data.portfolio.expected_daily_move.convexity_exposure)
        results["theta_exposures"].append(enhanced_state.data.portfolio.theta)
        results["vega_exposures"].append(enhanced_state.data.portfolio.expected_daily_move.volatility_exposure)
        
        # Print daily summary
        print(f"  SPX: {enhanced_state.data.market_conditions.spx:.2f}, VIX: {enhanced_state.data.market_conditions.vix:.2f}")
        print(f"  Portfolio Value: ${enhanced_state.data.portfolio.net_liquidation_value:.2f}")
        print(f"  P&L: ${enhanced_state.data.portfolio.pnl:.2f} ({enhanced_state.data.portfolio.pnl_percent:.2f}%)")
        print(f"  Delta Exposure: ${enhanced_state.data.portfolio.expected_daily_move.directional_exposure:.2f}")
        print(f"  Gamma Exposure: ${enhanced_state.data.portfolio.expected_daily_move.convexity_exposure:.2f}")
        print(f"  Theta: ${enhanced_state.data.portfolio.theta:.2f}")
        print(f"  Vega Exposure: ${enhanced_state.data.portfolio.expected_daily_move.volatility_exposure:.2f}")
    
    # Plot the results
    plot_simulation_results(results)
    
    return results

def plot_simulation_results(results):
    """
    Plot the simulation results.
    
    Args:
        results: Dictionary containing simulation results
    """
    # Create a figure with subplots
    fig, axs = plt.subplots(3, 2, figsize=(14, 12))
    fig.suptitle('Portfolio Performance Over a Week', fontsize=16)
    
    # Plot SPX and VIX
    axs[0, 0].plot(results["dates"], results["spx_values"], 'b-', marker='o')
    axs[0, 0].set_title('SPX Price')
    axs[0, 0].set_xlabel('Date')
    axs[0, 0].set_ylabel('Price')
    axs[0, 0].grid(True)
    
    axs[0, 1].plot(results["dates"], results["vix_values"], 'r-', marker='o')
    axs[0, 1].set_title('VIX Level')
    axs[0, 1].set_xlabel('Date')
    axs[0, 1].set_ylabel('VIX')
    axs[0, 1].grid(True)
    
    # Plot Portfolio P&L
    axs[1, 0].plot(results["dates"], results["portfolio_values"], 'g-', marker='o')
    axs[1, 0].set_title('Portfolio Value')
    axs[1, 0].set_xlabel('Date')
    axs[1, 0].set_ylabel('Value ($)')
    axs[1, 0].grid(True)
    
    # Plot Portfolio Greeks
    axs[1, 1].plot(results["dates"], results["delta_exposures"], 'b-', marker='o', label='Delta')
    axs[1, 1].plot(results["dates"], results["gamma_exposures"], 'r-', marker='o', label='Gamma')
    axs[1, 1].set_title('Portfolio Greeks')
    axs[1, 1].set_xlabel('Date')
    axs[1, 1].set_ylabel('Exposure ($)')
    axs[1, 1].legend()
    axs[1, 1].grid(True)
    
    # Plot Theta and Vega Exposures
    axs[2, 0].plot(results["dates"], results["theta_exposures"], 'b-', marker='o', label='Theta')
    axs[2, 0].plot(results["dates"], results["vega_exposures"], 'r-', marker='o', label='Vega')
    axs[2, 0].set_title('Theta and Vega Exposures')
    axs[2, 0].set_xlabel('Date')
    axs[2, 0].set_ylabel('Exposure ($)')
    axs[2, 0].legend()
    axs[2, 0].grid(True)
    
    # Plot Strategy P&Ls
    # axs[2, 1].plot(results["dates"], results["strategy_1_pnl"], 'b-', marker='o', label=results["strategy_1_name"].iloc[0])
    # axs[2, 1].plot(results["dates"], results["strategy_2_pnl"], 'r-', marker='o', label=results["strategy_2_name"].iloc[0])
    # axs[2, 1].set_title('Strategy P&Ls')
    # axs[2, 1].set_xlabel('Date')
    # axs[2, 1].set_ylabel('P&L ($)')
    # axs[2, 1].legend()
    # axs[2, 1].grid(True)
    
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig('portfolio_week_simulation.png')
    plt.show()

if __name__ == "__main__":
    print("Running portfolio week simulation...")
    results = run_week_simulation()
    
    # Save results to CSV
    # results.to_csv('portfolio_week_simulation_results.csv', index=False)
    print("\nSimulation complete. Results saved to portfolio_week_simulation_results.csv")
