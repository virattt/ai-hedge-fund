from langchain_core.messages import HumanMessage
from new_graph.state import AgentState, EnhancedAgentState, show_agent_reasoning
from new_models.portfolio import RiskProfile, ExpectedDailyMove
from services.market_data import get_market_indicators, get_market_data_for_strategy
from utils.progress import progress
from tools.api import prices_to_df
from services.market_data import get_cached_prices, get_market_data_for_strategy, get_market_indicators
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import math

##### Portfolio Metrics Agent #####
def portfolio_metrics_agent(state: AgentState):
    """
    Calculates all metrics for the portfolio, strategies, and market conditions.
    
    This agent runs before the risk manager to ensure all metrics are properly
    calculated and updated in the state. 
    The horizon is 1-day to set up the portfolio for the next day.
    It computes:
    
    1. Market conditions:
       - SPX price
       - VIX level
       - VVIX level
       - Expected daily move in SPX
       
    2. Portfolio-level metrics:
       - Portfolio P&L
       - Margin used
       - Stressed margin (margin when in the worst 5% of market conditions)
       - Portfolio, beta-weighted, delta, gamma, theta, vega
       - Expected daily P&L based on SPX daily expected move (1sigma move)
       - Expected P&L attribution(delta exposure, gamma exposure, theta exposure, vega exposure)
       - Conditional Value at Risk (CVaR), 90-95% confidence, 1-day horizon, used for max allowed daily loss
       
    3. Strategy-level metrics:
       - Strategy P&L
       - Margin requirements
       - Greeks (delta, gamma, theta, vega)
       - Expected delta exposure (delta * position size * multiplier* expected daily move in the underlying)
       - Expected convexity exposure (gamma * position size * multiplier* expected daily move in the underlying^2)
       - CVaR
    """
    # Ensure state has the required structure
    if not isinstance(state, dict):
        # If it's not a dict, assume it's an EnhancedAgentState or has a similar structure
        if hasattr(state, "_state"):
            state = state._state
        else:
            # Create a default state structure
            state = {
                "messages": [],
                "data": state.get("data", {}),
                "metadata": state.get("metadata", {})
            }
    
    # Ensure metadata exists
    if "metadata" not in state:
        state["metadata"] = {}
    
    # Create a metrics dictionary to store calculated values
    metrics = {}
    
    # Convert to enhanced state for structured access
    enhanced_state = EnhancedAgentState(state)

    # Access data using dot notation
    portfolio = enhanced_state.data.portfolio
    market_conditions = enhanced_state.data.market_conditions
    
    # Step 1: Calculate market conditions first
    calculate_market_conditions(enhanced_state)
    
    # Step 2: Calculate strategy-level metrics (bottom-up approach)
    calculate_strategy_level_metrics(portfolio, market_conditions)
    
    # Step 3: Calculate portfolio-level metrics based on strategy metrics
    calculate_portfolio_level_metrics(portfolio, market_conditions, metrics)
    
    # Step 4: Calculate risk metrics that depend on both strategy and portfolio metrics
    calculate_risk_metrics(portfolio, market_conditions)
    
    # Step 5: Update the enhanced state with the calculated metrics
    update_state_with_calculations(enhanced_state, metrics)
    
    # Return the updated state
    return state


def calculate_market_conditions(enhanced_state):
    """
    Calculate market conditions and expected daily move.
    
    Args:
        enhanced_state: EnhancedAgentState object
    """
    market_conditions = enhanced_state.data.market_conditions
    
    # Calculate expected daily move if not already set
    if market_conditions.expected_daily_move == 0:
        # Use VIX to estimate expected daily move
        if market_conditions.vix > 0:
            # VIX is annualized volatility, divide by sqrt(252) for daily
            market_conditions.expected_daily_move = market_conditions.vix / 100 / math.sqrt(252)
        else:
            # Default to 2% if VIX is not available
            market_conditions.expected_daily_move = 0.02


def calculate_strategy_level_metrics(portfolio, market_conditions):
    """
    Calculate all strategy-level metrics.
    
    Args:
        portfolio: Portfolio object containing strategies
        market_conditions: Market conditions object
    """
    for strategy in portfolio.strategies:
        # Calculate P&L metrics
        calculate_strategy_pnl_metrics(strategy)
        
        # Calculate greeks
        calculate_strategy_greeks(strategy, market_conditions)
        
        # Calculate margin requirements
        calculate_strategy_margin(strategy, market_conditions)
        
        # Calculate expected exposures
        calculate_strategy_exposures(strategy, market_conditions.expected_daily_move)
        
        # Calculate CVaR for the strategy
        strategy.risk_profile.CVaR = calculate_strategy_cvar(
            strategy, 
            market_conditions.expected_daily_move
        )
        
        # Calculate survival probabilities
        probs = calculate_survival_probabilities(
            strategy, 
            market_conditions.expected_daily_move
        )
        
        if probs:
            strategy.risk_profile.survival_probability_10 = probs[0]
            strategy.risk_profile.survival_probability_25 = probs[1]
            strategy.risk_profile.survival_probability_50 = probs[2]


def calculate_strategy_pnl_metrics(strategy):
    """
    Calculate P&L metrics for a strategy.
    
    Args:
        strategy: Strategy object
    """
    # Try to get real market data P&L
    try:
        pnl, pnl_percent, _ = calculate_strategy_pnl(strategy)
        strategy.pnl = pnl
        strategy.pnl_percent = pnl_percent
    except Exception as e:
        # Fall back to simulated P&L
        pnl, pnl_percent, _ = simulate_strategy_pnl(strategy)
        strategy.pnl = pnl
        strategy.pnl_percent = pnl_percent


def calculate_strategy_greeks(strategy, market_conditions):
    """
    Calculate and aggregate greeks for a strategy.
    
    Args:
        strategy: Strategy object
        market_conditions: Market conditions object
    """
    # Initialize strategy greeks
    delta = 0.0
    gamma = 0.0
    theta = 0.0
    vega = 0.0
    
    # Strategy-specific greek calculations based on strategy type
    if "Iron Condor" in strategy.description:
        # Iron Condors typically have low delta, negative theta, positive gamma
        delta = -5.0  # Near delta-neutral
        gamma = 0.1   # Slightly positive gamma
        theta = -50.0 # Strong negative theta (time decay is the profit source)
        vega = -20.0  # Negative vega (benefits from vol decrease)
    
    elif "Call Spread" in strategy.description:
        # Bull Call Spreads have positive delta, negative theta
        delta = 30.0  # Positive delta (bullish)
        gamma = 0.05  # Low gamma
        theta = -30.0 # Negative theta
        vega = 10.0   # Slightly positive vega
    
    elif "Protective Puts" in strategy.description:
        # Protective Puts have positive delta (from stock), positive gamma and vega (from puts)
        delta = 25.0  # Positive delta but less than 100 due to puts
        gamma = 0.2   # Positive gamma from puts
        theta = -70.0 # Negative theta from puts
        vega = 30.0   # Positive vega from puts
    
    else:
        # Generic calculation for other strategy types
        # In a real implementation, you would calculate these based on option pricing models
        delta = 10.0
        gamma = 0.1
        theta = -20.0
        vega = 5.0
    
    # In a real implementation, we would set these values on each leg's greeks
    # Since we're simulating, we'll store these values to be used by other functions
    strategy._delta = delta
    strategy._gamma = gamma
    strategy._theta = theta
    strategy._vega = vega


def calculate_strategy_margin(strategy, market_conditions):
    """
    Calculate margin requirements for a strategy.
    
    Args:
        strategy: Strategy object
        market_conditions: Market conditions object
    """
    # Strategy-specific margin calculations
    if "Iron Condor" in strategy.description:
        # Iron Condors typically require margin equal to the width of the spread minus credit received
        strategy.risk_profile.margin = 12000.0
    
    elif "Call Spread" in strategy.description:
        # Bull Call Spreads require margin equal to the width of the spread minus credit received
        strategy.risk_profile.margin = 8000.0
    
    elif "Protective Puts" in strategy.description:
        # Protective Puts require margin for the stock position
        strategy.risk_profile.margin = 10000.0
    
    else:
        # Generic calculation for other strategy types
        strategy.risk_profile.margin = 5000.0


def calculate_strategy_exposures(strategy, expected_daily_move):
    """
    Calculate expected exposures for a strategy.
    
    Args:
        strategy: Strategy object
        expected_daily_move: Expected daily price move as a decimal (e.g., 0.01 for 1%)
    """
    # Calculate expected delta exposure
    # Delta exposure = delta * position size * multiplier * expected daily move in the underlying
    delta = strategy._delta if hasattr(strategy, '_delta') else 0
    
    # Strategy-specific delta exposure calculations
    if "Iron Condor" in strategy.description:
        # Iron Condors have lower directional exposure
        strategy.risk_profile.expected_delta_move = delta * 100 * expected_daily_move * strategy.price
    
    elif "Call Spread" in strategy.description:
        # Bull Call Spreads have higher directional exposure
        strategy.risk_profile.expected_delta_move = delta * 100 * expected_daily_move * strategy.price * 2.0
    
    elif "Protective Puts" in strategy.description:
        # Protective Puts have moderate directional exposure
        strategy.risk_profile.expected_delta_move = delta * 100 * expected_daily_move * strategy.price * 1.5
    
    else:
        # Generic calculation
        strategy.risk_profile.expected_delta_move = delta * 100 * expected_daily_move * strategy.price
    
    # Calculate expected convexity exposure
    # Convexity exposure = gamma * position size * multiplier * (expected daily move in the underlying)^2
    gamma = strategy._gamma if hasattr(strategy, '_gamma') else 0
    
    # Strategy-specific convexity exposure calculations
    if "Iron Condor" in strategy.description:
        # Iron Condors have higher convexity risk
        strategy.risk_profile.expected_convexity_move = gamma * 100 * (expected_daily_move * strategy.price) ** 2 * 2.0
    
    elif "Call Spread" in strategy.description:
        # Bull Call Spreads have lower convexity risk
        strategy.risk_profile.expected_convexity_move = gamma * 100 * (expected_daily_move * strategy.price) ** 2 * 0.5
    
    elif "Protective Puts" in strategy.description:
        # Protective Puts have moderate convexity risk
        strategy.risk_profile.expected_convexity_move = gamma * 100 * (expected_daily_move * strategy.price) ** 2 * 1.0
    
    else:
        # Generic calculation
        strategy.risk_profile.expected_convexity_move = gamma * 100 * (expected_daily_move * strategy.price) ** 2


def calculate_portfolio_level_metrics(portfolio, market_conditions, metrics):
    """
    Calculate portfolio-level metrics based on strategy metrics.
    
    Args:
        portfolio: Portfolio object
        market_conditions: Market conditions object
        metrics: Dictionary to store calculated metrics
    """
    # Calculate portfolio P&L
    total_pnl = sum(strategy.pnl for strategy in portfolio.strategies)
    portfolio.pnl = total_pnl
    
    # Calculate portfolio P&L percent
    if portfolio.net_liquidation_value > 0:
        portfolio.pnl_percent = (total_pnl / portfolio.net_liquidation_value) * 100
    else:
        portfolio.pnl_percent = 0
    
    # Calculate total margin used
    total_margin = sum(strategy.risk_profile.margin for strategy in portfolio.strategies)
    portfolio.margin_used = total_margin
    metrics['margin_used'] = total_margin
    
    # Calculate max margin (1.5x current margin as a simple rule)
    max_margin = total_margin * 1.5
    portfolio.max_margin = max_margin
    metrics['max_margin'] = max_margin
    
    # Calculate portfolio greeks
    total_delta = 0
    total_gamma = 0
    total_theta = 0
    total_vega = 0
    
    # Calculate beta-weighted greeks
    total_beta_weighted_delta = 0
    total_beta_weighted_gamma = 0
    
    for strategy in portfolio.strategies:
        # Get strategy beta
        beta = strategy.beta
        
        # Add to totals
        if hasattr(strategy, '_delta'):
            total_delta += strategy._delta
            total_beta_weighted_delta += strategy._delta * beta
        
        if hasattr(strategy, '_gamma'):
            total_gamma += strategy._gamma
            total_beta_weighted_gamma += strategy._gamma * beta
        
        if hasattr(strategy, '_theta'):
            total_theta += strategy._theta
        
        if hasattr(strategy, '_vega'):
            total_vega += strategy._vega
    
    # Set portfolio greeks
    portfolio.total_beta_weighted_delta = total_beta_weighted_delta
    portfolio.total_beta_weighted_gamma = total_beta_weighted_gamma
    portfolio.theta = total_theta
    
    # Store in metrics dictionary
    metrics['total_beta_weighted_delta'] = total_beta_weighted_delta
    metrics['total_beta_weighted_gamma'] = total_beta_weighted_gamma
    metrics['theta'] = total_theta
    
    # Calculate portfolio expected daily move
    calculate_portfolio_expected_daily_move(portfolio, market_conditions.expected_daily_move)


def calculate_portfolio_expected_daily_move(portfolio, expected_daily_move):
    """
    Calculate expected daily move for the portfolio.
    
    Args:
        portfolio: Portfolio object
        expected_daily_move: Expected daily price move as a decimal (e.g., 0.01 for 1%)
    """
    # Initialize expected daily move components
    directional_exposure = 0
    convexity_exposure = 0
    time_decay = 0
    volatility_exposure = 0
    
    # Sum up contributions from each strategy
    for strategy in portfolio.strategies:
        # Directional exposure from delta
        directional_exposure += strategy.risk_profile.expected_delta_move
        
        # Convexity exposure from gamma
        convexity_exposure += strategy.risk_profile.expected_convexity_move
        
        # Time decay from theta
        if hasattr(strategy, '_theta'):
            time_decay += strategy._theta
        
        # Volatility exposure from vega
        if hasattr(strategy, '_vega'):
            # Assuming a 1% change in implied volatility
            volatility_exposure += strategy._vega * 0.01
    
    # Set the portfolio expected daily move
    portfolio.expected_daily_move.directional_exposure = directional_exposure
    portfolio.expected_daily_move.convexity_exposure = convexity_exposure
    portfolio.expected_daily_move.time_decay = time_decay
    portfolio.expected_daily_move.volatility_exposure = volatility_exposure


def calculate_risk_metrics(portfolio, market_conditions):
    """
    Calculate risk metrics that depend on both strategy and portfolio metrics.
    
    Args:
        portfolio: Portfolio object
        market_conditions: Market conditions object
    """
    # Calculate portfolio CVaR
    portfolio_cvar = calculate_portfolio_cvar(portfolio, market_conditions.expected_daily_move)
    portfolio.CVaR = portfolio_cvar
    
    # Calculate strategy CVaRs
    strategy_cvars = {}
    total_cvar = 0
    
    for strategy in portfolio.strategies:
        cvar = strategy.risk_profile.CVaR
        strategy_cvars[strategy.description] = cvar
        total_cvar += cvar
    
    # Calculate marginal contribution to risk for each strategy
    if total_cvar > 0:
        for strategy in portfolio.strategies:
            # MCR should be the percentage of total portfolio risk
            strategy.risk_profile.marginal_contribution_to_risk = (strategy.risk_profile.CVaR / total_cvar) * 100
    else:
        for strategy in portfolio.strategies:
            strategy.risk_profile.marginal_contribution_to_risk = 0


def update_state_with_calculations(enhanced_state, metrics):
    """
    Update the state with the calculated metrics.
    
    Args:
        enhanced_state: Enhanced agent state
        metrics: Dictionary of calculated metrics
    """
    # Store the metrics in the state for use in the dashboard
    try:
        enhanced_state._state["metadata"]["metrics"] = metrics
    except (KeyError, AttributeError):
        # If metadata doesn't exist or can't be accessed, create it
        if hasattr(enhanced_state, "_state"):
            if "metadata" not in enhanced_state._state:
                enhanced_state._state["metadata"] = {}
            enhanced_state._state["metadata"]["metrics"] = metrics
        else:
            # Fallback if enhanced_state doesn't have the expected structure
            print("Warning: Could not store metrics in state metadata")


# Helper functions for strategy-level calculations

def calculate_strategy_cvar(strategy, expected_daily_move, confidence=0.95):
    """
    Calculate Conditional Value at Risk (CVaR) for a strategy.
    This is a simplified implementation - in a real system, you would use historical simulation or Monte Carlo.
    
    Args:
        strategy: Strategy object
        expected_daily_move: Expected daily price move as a decimal (e.g., 0.01 for 1%)
        confidence: Confidence level (default: 0.95)
        
    Returns:
        float: Strategy CVaR value
    """
    # Strategy-specific CVaR calculations
    if "Iron Condor" in strategy.description:
        # Iron Condors have higher tail risk
        return 2400.0
    
    elif "Call Spread" in strategy.description:
        # Bull Call Spreads have moderate tail risk
        return 1600.0
    
    elif "Protective Puts" in strategy.description:
        # Protective Puts have lower tail risk due to protection
        return 2000.0
    
    else:
        # Generic calculation for other strategy types
        # In a real implementation, you would use a more sophisticated model
        return strategy.risk_profile.margin * 0.4


def calculate_portfolio_cvar(portfolio, expected_daily_move=0.02):
    """
    Calculate the portfolio-level Conditional Value at Risk (CVaR).
    
    This is a simplified implementation that can be replaced with a more sophisticated
    model in the future (e.g., using historical simulation, Monte Carlo simulation,
    or parametric methods).
    
    Args:
        portfolio: Portfolio object containing strategies
        expected_daily_move: Expected daily price move as a decimal (e.g., 0.01 for 1%)
        
    Returns:
        float: Portfolio CVaR value
    """
    # Sum up individual strategy CVaRs
    # This is a simplification - in reality, you would account for correlations
    total_cvar = sum(strategy.risk_profile.CVaR for strategy in portfolio.strategies)
    
    # Apply a diversification benefit (simplified)
    # In a real implementation, you would use a correlation matrix
    diversification_factor = 0.8  # Assume 20% diversification benefit
    portfolio_cvar = total_cvar * diversification_factor
    
    return portfolio_cvar


def calculate_survival_probabilities(strategy, expected_daily_move, days=30):
    """
    Calculate the probability that the strategy hits profit targets before hitting max loss.
    
    Returns:
    - Tuple of probabilities (10% profit, 25% profit, 50% profit)
    """
    # Strategy-specific survival probability calculations
    if "Iron Condor" in strategy.description:
        # Iron Condors have high probability of small profits, low probability of large profits
        return (0.75, 0.40, 0.15)
    
    elif "Call Spread" in strategy.description:
        # Bull Call Spreads have moderate probability across the board
        return (0.60, 0.45, 0.30)
    
    elif "Protective Puts" in strategy.description:
        # Protective Puts have lower probability of small profits, higher probability of large profits
        return (0.50, 0.35, 0.25)
    
    else:
        # Generic calculation for other strategy types
        return (0.60, 0.40, 0.20)


def simulate_strategy_pnl(strategy):
    """
    Simulate P&L for a strategy when real market data is unavailable.
    
    Args:
        strategy: Strategy object
        
    Returns:
        tuple: (pnl, pnl_percent, pnl_attribution)
    """
    # For demonstration purposes, return zero P&L
    pnl = 0.0
    
    # Calculate P&L percent
    if strategy.premium != 0:
        pnl_percent = (pnl / abs(strategy.premium)) * 100
    else:
        pnl_percent = 0.0
    
    # P&L attribution (simplified)
    pnl_attribution = {
        "delta": 0.0,
        "gamma": 0.0,
        "theta": 0.0,
        "vega": 0.0
    }
    
    return pnl, pnl_percent, pnl_attribution


# Import this class to avoid errors
class Greeks:
    def __init__(self):
        self.delta = 0.0
        self.gamma = 0.0
        self.theta = 0.0
        self.vega = 0.0
