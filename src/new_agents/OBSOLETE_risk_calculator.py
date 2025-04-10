from langchain_core.messages import HumanMessage
from graph.state import AgentState, EnhancedAgentState, show_agent_reasoning
from utils.progress import progress
from tools.api import prices_to_df
from services.market_data import get_cached_prices, get_market_data_for_strategy, get_market_indicators
import json
import numpy as np
import math
from datetime import datetime, timedelta
import os
import pickle
from functools import lru_cache

# Initialize the market data cache
# Removed MarketDataCache class and related code
@lru_cache(maxsize=128)

##### Risk Calculator Agent #####
def risk_calculator_agent(state: AgentState):
    """
    Calculates risk parameters for the portfolio and each strategy.
    
    This agent runs before the risk manager to ensure all risk metrics are properly
    calculated and updated in the state. 
    The horizon is 1-day to set up the portfolio for the next day.
    It computes:
    
    1. Portfolio-level metrics:
       - Portfolio P&L
       - Margin used
       - Stressed margin (margin when in the worst 5% of market conditions)
       - Portfolio, beta-weighted, delta, gamma, theta, vega
       - Expected daily P&L based on SPX daily expected move (1sigma move)
       - Expected P&L attribution(delta exposure, gamma exposure, theta exposure, vega exposure)
       - Conditional Value at Risk (CVaR), 90-95% confidence, 1-day horizon, used for max allowed daily loss
       
    2. Strategy-level metrics:
       - Strategy P&L
       - Margin requirements
       - Greeks (delta, gamma, theta, vega)
       - Expected delta exposure (delta * position size * multiplier* expected daily move in the underlying)
       - Expected convexity exposure (gamma * position size * multiplier* expected daily move in the underlying^2)
       - CVaR
    """
    # Convert to enhanced state for structured access
    enhanced_state = EnhancedAgentState(state)

    # Access data using dot notation
    portfolio = enhanced_state.data.portfolio
    market_conditions = enhanced_state.data.market_conditions
    
    # Get market data for calculations
    spx_price = market_conditions.spx
    vix_level = market_conditions.vix
    expected_daily_move = market_conditions.one_day_expected_move
    
    # Step 1: Calculate strategy-level metrics first (bottom-up approach)
    calculate_strategy_level_metrics(portfolio, market_conditions)
    
    # Step 2: Calculate portfolio-level metrics based on strategy metrics
    calculate_portfolio_level_metrics(portfolio, market_conditions)
    
    # Step 3: Calculate risk metrics that depend on both strategy and portfolio metrics
    calculate_risk_metrics(portfolio, market_conditions)
    
    # Step 4: Update the enhanced state with the calculated metrics
    update_state_with_calculations(enhanced_state)
    
    # Return the updated state
    return enhanced_state.to_dict()


def calculate_strategy_level_metrics(portfolio, market_conditions):
    """
    Calculate all strategy-level metrics.
    
    Args:
        portfolio: Portfolio object containing strategies
        market_conditions: Market conditions object
    """
    # Get expected daily move from market conditions
    expected_daily_move = market_conditions.one_day_expected_move
    
    # Calculate metrics for each strategy
    for strategy in portfolio.strategies:
        # Calculate strategy P&L
        calculate_strategy_pnl_metrics(strategy)
        
        # Calculate strategy greeks
        calculate_strategy_greeks(strategy)
        
        # Calculate strategy margin requirements
        calculate_strategy_margin(strategy, market_conditions)
        
        # Calculate strategy expected exposures
        calculate_strategy_exposures(strategy, expected_daily_move)
        
        # Calculate strategy CVaR
        strategy.risk_profile.CVaR = calculate_strategy_cvar(
            strategy, 
            expected_daily_move
        )


def calculate_strategy_pnl_metrics(strategy):
    """
    Calculate P&L metrics for a strategy.
    
    Args:
        strategy: Strategy object
    """
    try:
        # Try to calculate P&L using real market data
        strategy, pnl_attribution = update_strategy_pnl(strategy)
    except Exception as e:
        # Fall back to simulation if real data is unavailable
        progress.update_status("risk_calculator", strategy.ticker, 
                              f"Error calculating P&L with real data: {str(e)}. Using simulation.")
        strategy.pnl, strategy.pnl_percent, _ = simulate_strategy_pnl(strategy)


def calculate_strategy_greeks(strategy):
    """
    Calculate and aggregate greeks for a strategy.
    
    Args:
        strategy: Strategy object
    """
    # Initialize aggregated greeks
    total_delta = 0.0
    total_gamma = 0.0
    total_theta = 0.0
    total_vega = 0.0
    
    # Sum up greeks from all legs
    for leg in strategy.legs:
        # Get position size and multiplier
        position_size = leg.position_size
        multiplier = getattr(leg, "multiplier", 1.0)
        
        # Get greeks from the leg
        if hasattr(leg, "greeks"):
            # Calculate weighted greeks
            delta = leg.greeks.delta * position_size * multiplier
            gamma = leg.greeks.gamma * position_size * multiplier
            theta = leg.greeks.theta * position_size * multiplier
            vega = leg.greeks.vega * position_size * multiplier
            
            # Add to totals
            total_delta += delta
            total_gamma += gamma
            total_theta += theta
            total_vega += vega
    
    # Store aggregated greeks in the strategy
    strategy.greeks.delta = total_delta
    strategy.greeks.gamma = total_gamma
    strategy.greeks.theta = total_theta
    strategy.greeks.vega = total_vega


def calculate_strategy_margin(strategy, market_conditions):
    """
    Calculate margin requirements for a strategy.
    
    Args:
        strategy: Strategy object
        market_conditions: Market conditions object
    """
    # Base margin calculation
    base_margin = abs(strategy.premium) * 1.5  # 150% of premium as a simple baseline
    
    # Adjust margin based on strategy type and market conditions
    if strategy.risk_profile.risk_category == "defined":
        # For defined risk strategies, max loss is known
        strategy.risk_profile.margin = abs(strategy.premium)
    else:
        # For undefined risk, use a more conservative estimate
        vix_adjustment = market_conditions.vix / 20.0  # Higher VIX = higher margin
        strategy.risk_profile.margin = base_margin * (1.0 + vix_adjustment)


def calculate_strategy_exposures(strategy, expected_daily_move):
    """
    Calculate expected exposures for a strategy.
    
    Args:
        strategy: Strategy object
        expected_daily_move: Expected daily move of the underlying
    """
    # Get strategy greeks
    delta = strategy.greeks.delta
    gamma = strategy.greeks.gamma
    
    # Calculate expected delta exposure
    strategy.risk_profile.expected_delta_move = delta * expected_daily_move
    
    # Calculate expected convexity exposure (gamma * expected_move^2)
    strategy.risk_profile.expected_convexity_move = 0.5 * gamma * (expected_daily_move ** 2)


def calculate_portfolio_level_metrics(portfolio, market_conditions):
    """
    Calculate portfolio-level metrics based on strategy metrics.
    
    Args:
        portfolio: Portfolio object containing strategies
        market_conditions: Market conditions object
    """
    # Initialize portfolio metrics
    total_pnl = 0.0
    total_margin = 0.0
    total_beta_weighted_delta = 0.0
    total_beta_weighted_gamma = 0.0
    total_theta = 0.0
    
    # Calculate expected daily move
    expected_daily_move = market_conditions.one_day_expected_move
    
    # Aggregate metrics from all strategies
    for strategy in portfolio.strategies:
        # Get strategy beta
        beta = get_strategy_beta(strategy)
        
        # Add to portfolio P&L
        total_pnl += strategy.pnl
        
        # Add to portfolio margin
        total_margin += strategy.risk_profile.margin
        
        # Add to portfolio beta-weighted delta
        total_beta_weighted_delta += strategy.greeks.delta * beta
        
        # Add to portfolio beta-weighted gamma
        total_beta_weighted_gamma += strategy.greeks.gamma * beta
        
        # Add to portfolio theta
        total_theta += strategy.greeks.theta
    
    # Update portfolio metrics
    portfolio.pnl = total_pnl
    portfolio.margin_used = total_margin
    portfolio.total_beta_weighted_delta = total_beta_weighted_delta
    portfolio.total_beta_weighted_gamma = total_beta_weighted_gamma
    portfolio.theta = total_theta
    
    # Calculate expected daily move components
    calculate_portfolio_expected_daily_move(portfolio, expected_daily_move)


def get_strategy_beta(strategy):
    """
    Get beta for a strategy, either from cached data or by calculating it.
    
    Args:
        strategy: Strategy object
        
    Returns:
        float: Beta value for the strategy
    """
    # Check if beta is already calculated
    if hasattr(strategy, "beta") and strategy.beta is not None:
        return strategy.beta
    
    # Default beta is 1.0 if we can't calculate it
    beta = 1.0
    
    try:
        # Try to get historical prices for beta calculation
        ticker = strategy.ticker
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        
        # Get price data
        prices = get_cached_prices(ticker, start_date, end_date)
        
        # Convert to dataframe
        if prices and "prices" in prices:
            prices_df = prices_to_df(prices["prices"])
            
            # Calculate beta
            beta = calculate_beta(prices_df, ticker)
    except Exception as e:
        progress.update_status("risk_calculator", strategy.ticker, 
                              f"Error calculating beta: {str(e)}. Using default beta of 1.0.")
    
    # Store beta in strategy for future use
    strategy.beta = beta
    
    return beta


def calculate_portfolio_expected_daily_move(portfolio, expected_daily_move):
    """
    Calculate expected daily move components for the portfolio.
    
    Args:
        portfolio: Portfolio object
        expected_daily_move: Expected daily move of the market
    """
    # Calculate directional exposure (delta * expected move)
    portfolio.expected_daily_move.directional_exposure = portfolio.total_beta_weighted_delta * expected_daily_move
    
    # Calculate convexity exposure (0.5 * gamma * expected_move^2)
    portfolio.expected_daily_move.convexity_exposure = 0.5 * portfolio.total_beta_weighted_gamma * (expected_daily_move ** 2)
    
    # Time decay is just theta
    portfolio.expected_daily_move.time_decay = portfolio.theta
    
    # Calculate volatility exposure (simplified)
    # In a real implementation, you would use vega and expected vol change
    portfolio.expected_daily_move.volatility_exposure = 0.0


def calculate_risk_metrics(portfolio, market_conditions):
    """
    Calculate risk metrics that depend on both strategy and portfolio metrics.
    
    Args:
        portfolio: Portfolio object
        market_conditions: Market conditions object
    """
    # Get expected daily move
    expected_daily_move = market_conditions.one_day_expected_move
    
    # Calculate portfolio CVaR
    portfolio.CVaR = calculate_portfolio_cvar(portfolio, expected_daily_move)
    
    # Get strategy CVaRs for marginal contribution calculation
    strategy_cvars = {i: strategy.risk_profile.CVaR 
                     for i, strategy in enumerate(portfolio.strategies)}
    
    # Calculate marginal contribution to risk
    calculate_marginal_contribution_to_risk(portfolio, strategy_cvars, portfolio.CVaR)
    
    # Calculate stressed margin (margin in worst 5% of market conditions)
    # This is a simplified calculation - in a real system, you would use historical stress testing
    stress_factor = 2.0  # Assume twice the normal margin in stressed conditions
    portfolio.max_margin = portfolio.margin_used * stress_factor


def update_state_with_calculations(enhanced_state):
    """
    Update the enhanced state with all calculated metrics.
    
    Args:
        enhanced_state: EnhancedAgentState object
    """
    # The state is already updated since we're working with references
    # This function is a placeholder for any final state updates or validations
    
    # Log completion of risk calculations
    progress.update_status("risk_calculator", "portfolio", "Risk calculations completed")


def get_cached_prices(ticker, start_date, end_date):
    """
    Get cached price data or fetch from API if not available.
    Uses both the MarketDataCache and Python's lru_cache for efficiency.
    """
    # Removed cache_key and market_data_cache usage
    # If not in cache, fetch from API
    progress.update_status("market_data_cache", ticker, "Fetching price data from API")
    prices = get_prices(ticker=ticker, start_date=start_date, end_date=end_date)
    
    # Removed market_data_cache.set usage
    
    return prices


@lru_cache(maxsize=128)
def get_prices(ticker, start_date, end_date):
    """
    Get cached price data or fetch from API if not available.
    Uses Python's lru_cache for efficiency.
    
    This function now relies on the centralized market data service.
    
    Args:
        ticker (str): The ticker symbol
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        
    Returns:
        dict: Price data for the ticker
    """
    # Use the centralized market data service
    progress.update_status("risk_calculator", ticker, "Fetching price data from market data service")
    return get_cached_prices(ticker=ticker, start_date=start_date, end_date=end_date)


def format_market_data_for_pnl(market_data, strategy):
    """
    Format generic market data from the market data service specifically for P&L calculations.
    
    Args:
        market_data (dict): Raw market data from the market data service
        strategy: Strategy object containing legs and other information
        
    Returns:
        dict: Formatted market data for P&L calculations
    """
    # Initialize the formatted data structure with default values
    formatted_data = {
        "underlying_price": None,
        "prev_underlying_price": None,
        "legs_data": [],
        "days_passed": 1,  # Default to 1 day for daily P&L
        "timestamp": datetime.now().isoformat()
    }
    
    # Extract underlying price data from market data
    if market_data and "underlying" in market_data and market_data["underlying"]:
        formatted_data["underlying_price"] = market_data["underlying"].get("current_price")
        formatted_data["prev_underlying_price"] = market_data["underlying"].get("previous_price")
    
    # If we have historical data, calculate days passed more accurately
    if "historical" in market_data and "prices" in market_data["historical"]:
        historical_prices = market_data["historical"]["prices"]
        if len(historical_prices) > 1:
            # Calculate days between the last two data points
            try:
                last_date = datetime.strptime(historical_prices[-1]["date"], "%Y-%m-%d")
                prev_date = datetime.strptime(historical_prices[-2]["date"], "%Y-%m-%d")
                formatted_data["days_passed"] = (last_date - prev_date).days
            except (KeyError, ValueError, IndexError):
                # Keep default if there's an issue with the dates
                pass
    
    # Process each leg in the strategy
    for i, leg in enumerate(strategy.legs):
        # Handle DotDict objects by using dictionary-style access
        leg_data = {
            "id": i,  # Use index as ID if not available
            "type": leg["type"] if isinstance(leg, dict) else getattr(leg, "type", "unknown"),
            "position_type": leg["position_type"] if isinstance(leg, dict) else getattr(leg, "position_type", "unknown"),
            "position_size": leg["position_size"] if isinstance(leg, dict) else getattr(leg, "position_size", 0),
            "cost_basis": leg["cost_basis"] if isinstance(leg, dict) else getattr(leg, "cost_basis", 0),
            "multiplier": leg["multiplier"] if isinstance(leg, dict) and "multiplier" in leg else getattr(leg, "multiplier", 1),
            "current_price": None,
            "previous_price": None,
            "implied_vol": None,
            "prev_implied_vol": None,
            "greeks": {}
        }
        
        # For options, get data from the option chain
        if leg_data["type"] == "option" and "options" in market_data:
            option_data = get_option_data_for_leg(leg, market_data["options"])
            if option_data:
                leg_data.update({
                    "current_price": option_data.get("last"),
                    "bid": option_data.get("bid"),
                    "ask": option_data.get("ask"),
                    "implied_vol": option_data.get("implied_volatility"),
                    "greeks": {
                        "delta": option_data.get("delta"),
                        "gamma": option_data.get("gamma"),
                        "theta": option_data.get("theta"),
                        "vega": option_data.get("vega")
                    }
                })
        
        # For stocks, use the underlying price
        elif leg_data["type"] == "stock" and formatted_data["underlying_price"] is not None:
            leg_data["current_price"] = formatted_data["underlying_price"]
            leg_data["previous_price"] = formatted_data["prev_underlying_price"]
            # Stock greeks are simpler
            leg_data["greeks"] = {
                "delta": 1.0 if leg_data["position_type"] == "long" else -1.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0
            }
        
        # Add to the formatted data
        formatted_data["legs_data"].append(leg_data)
    
    return formatted_data


def get_option_data_for_leg(leg, option_chain):
    """
    Get option data for a specific leg from the option chain.
    
    Args:
        leg: Option leg from the strategy
        option_chain: Option chain data from market data service
        
    Returns:
        dict: Option data for the leg or None if not found
    """
    # Handle both object and dictionary access patterns
    if isinstance(leg, dict):
        leg_type = leg.get("type")
        position_type = leg.get("position_type")
        strike = leg.get("strike")
        expiry = leg.get("expiry")
        option_type = leg.get("option_type", "").lower()
    else:
        leg_type = getattr(leg, "type", None)
        position_type = getattr(leg, "position_type", None)
        strike = getattr(leg, "strike", None)
        expiry = getattr(leg, "expiry", None)
        option_type = getattr(leg, "option_type", "").lower()
    
    # Only process option legs
    if leg_type != "option":
        return None
    
    # Handle the specific option chain structure we have
    if not isinstance(option_chain, dict):
        return None
    
    # Determine if it's a call or put
    option_category = "calls" if option_type == "call" else "puts"
    
    # Check if the category exists in the option chain
    if option_category not in option_chain:
        return None
    
    # Find the closest strike and expiry
    closest_option = None
    min_diff = float('inf')
    
    # The options data might be organized by expiry and strike
    options_list = []
    
    # Extract all options from the chain
    if isinstance(option_chain[option_category], dict):
        # Nested structure by expiry and strike
        for expiry_key, strikes in option_chain[option_category].items():
            if isinstance(strikes, dict):
                for strike_key, option_data in strikes.items():
                    if isinstance(option_data, dict):
                        options_list.append(option_data)
    elif isinstance(option_chain[option_category], list):
        # Flat list of options
        options_list = option_chain[option_category]
    
    # Find the closest match
    for option in options_list:
        if not isinstance(option, dict):
            continue
            
        option_strike = option.get("strike", 0)
        option_expiry = option.get("expiry", "")
        
        # Calculate a score based on how close this option is to what we want
        strike_diff = abs(float(option_strike) - float(strike)) if option_strike and strike else float('inf')
        
        # If expiry matches exactly, prioritize it
        expiry_match = 0 if option_expiry == expiry else 1
        
        # Combined score (prioritize expiry match, then strike closeness)
        score = expiry_match * 1000 + strike_diff
        
        if score < min_diff:
            min_diff = score
            closest_option = option
    
    return closest_option


def calculate_strategy_pnl(strategy):
    """
    Calculate the current P&L for a strategy based on real market data.
    
    Args:
        strategy: Strategy object containing legs and other information
        
    Returns:
        tuple: (pnl, pnl_percent, attribution)
    """
    from services.market_data import get_market_data_for_strategy
    
    # Get market data for the strategy
    market_data = get_market_data_for_strategy(strategy)
    
    # Format the market data for P&L calculations
    formatted_data = format_market_data_for_pnl(market_data, strategy)
    
    # Initialize P&L components
    total_pnl = 0.0
    delta_pnl = 0.0
    gamma_pnl = 0.0
    theta_pnl = 0.0
    vega_pnl = 0.0
    
    # Calculate P&L for each leg
    for i, leg_data in enumerate(formatted_data["legs_data"]):
        leg = strategy.legs[i]
        
        # Skip if we don't have current price data
        if leg_data["current_price"] is None:
            continue
            
        # Calculate the leg's P&L
        cost_basis = leg_data["cost_basis"]
        current_price = leg_data["current_price"]
        position_size = leg_data["position_size"]
        multiplier = leg_data["multiplier"]
        
        # Calculate the raw P&L for this leg
        leg_pnl = (current_price - cost_basis) * position_size * multiplier
        
        # Add to total P&L
        total_pnl += leg_pnl
        
        # Calculate P&L attribution if we have the data
        if leg_data["greeks"]:
            # Delta P&L
            delta = leg_data["greeks"].get("delta", 0)
            underlying_change = formatted_data["underlying_price"] - formatted_data["prev_underlying_price"]
            delta_pnl += delta * underlying_change * abs(position_size) * multiplier
        
            # Gamma P&L (1/2 * gamma * (price change)^2)
            gamma = leg_data["greeks"].get("gamma", 0)
            gamma_pnl += 0.5 * gamma * (underlying_change ** 2) * abs(position_size) * multiplier
        
            # Theta P&L (time decay)
            theta = leg_data["greeks"].get("theta", 0)
            days_passed = formatted_data["days_passed"]
            theta_pnl += theta * days_passed * abs(position_size) * multiplier
        
            # Vega P&L (volatility change)
            vega = leg_data["greeks"].get("vega", 0)
            if leg_data["implied_vol"] is not None and leg_data["prev_implied_vol"] is not None:
                vol_change = (leg_data["implied_vol"] - leg_data["prev_implied_vol"]) * 100  # Convert to percentage points
                vega_pnl += vega * vol_change * abs(position_size) * multiplier
        
    # Calculate P&L as a percentage of the premium
    premium = abs(strategy.premium) if hasattr(strategy, "premium") and strategy.premium != 0 else 1.0
    pnl_percent = (total_pnl / premium) * 100
    
    # Calculate unexplained P&L (the remainder)
    explained_pnl = delta_pnl + gamma_pnl + theta_pnl + vega_pnl
    unexplained_pnl = total_pnl - explained_pnl
    
    # Create the attribution dictionary
    attribution = {
        "delta": delta_pnl,
        "gamma": gamma_pnl,
        "theta": theta_pnl,
        "vega": vega_pnl,
        "other": unexplained_pnl
    }
    
    return total_pnl, pnl_percent, attribution


def update_strategy_pnl(strategy):
    """
    Update a strategy's P&L fields based on current market conditions.
    
    Args:
        strategy: Strategy object to update
        
    Returns:
        Strategy: Updated strategy with P&L fields
    """
    # Calculate P&L
    pnl, pnl_percent, pnl_attribution = calculate_strategy_pnl(strategy)
    
    # Update strategy fields
    strategy.pnl = pnl
    strategy.pnl_percent = pnl_percent
    
    # Update P&L history
    current_date = datetime.now().strftime("%Y-%m-%d")
    if not hasattr(strategy, "pnl_history"):
        strategy.pnl_history = {}
    strategy.pnl_history[current_date] = pnl
    
    return strategy, pnl_attribution


def calculate_beta(prices_df, ticker, window=60):
    """
    Calculate beta of a ticker relative to SPX.
    In a real implementation, you would use proper regression with actual SPX data.
    """
    # For a real implementation, you would:
    # 1. Get SPX returns for the same period
    # 2. Calculate daily returns for both the ticker and SPX
    # 3. Calculate beta = covariance(ticker, SPX) / variance(SPX)
    
    # Simplified beta calculation based on ticker characteristics
    if ticker in ["SPY", "IVV", "VOO"]:
        return 1.0
    elif ticker in ["QQQ", "AAPL", "MSFT", "GOOGL", "AMZN"]:
        return 1.2
    elif ticker in ["XLK", "XLC"]:
        return 1.1
    elif ticker in ["XLF", "XLI", "XLB"]:
        return 0.9
    elif ticker in ["XLU", "XLP", "USMV", "XLV"]:
        return 0.7
    elif ticker in ["GLD", "SLV"]:
        return 0.3
    elif ticker in ["TLT", "IEF"]:
        return -0.3  # Negative beta for treasuries
    else:
        return 1.0


def calculate_strategy_cvar(strategy, expected_daily_move, confidence=0.95):
    """
    Calculate Conditional Value at Risk (CVaR) for a strategy.
    This is a simplified implementation - in a real system, you would use historical simulation or Monte Carlo.
    """
    # In a real implementation, you would:
    # 1. Simulate many possible market scenarios
    # 2. Calculate P&L for each scenario
    # 3. Take the average of the worst (1-confidence)% of scenarios
    
    # For demonstration, use a simple approximation based on strategy characteristics
    if strategy.risk_profile.risk_category == "defined":
        # For defined risk, CVaR is close to the max loss (premium paid)
        return abs(strategy.premium) * 0.9
    else:
        # For undefined risk, estimate based on delta and gamma
        delta_impact = strategy.risk_profile.expected_delta_move
        gamma_impact = strategy.risk_profile.expected_convexity_move
        
        # Stress test: assume a 3-sigma move
        stress_move = expected_daily_move * 3
        stress_impact = (strategy.risk_profile.expected_delta_move * 3) + (strategy.risk_profile.expected_convexity_move * 9)
        
        return abs(stress_impact)


def calculate_portfolio_cvar(portfolio, expected_daily_move=0.02):
    """
    Calculate the portfolio-level Conditional Value at Risk (CVaR).
    
    This is a simplified implementation that can be replaced with a more sophisticated
    model in the future (e.g., using historical simulation, Monte Carlo simulation,
    or parametric methods).
    
    Args:
        portfolio: Portfolio object containing strategies
        expected_daily_move: Expected daily move of the market (default: 2%)
        
    Returns:
        float: Portfolio CVaR value
    """
    # Initialize the total CVaR
    portfolio_cvar = 0.0
    
    # Get the total portfolio value
    portfolio_value = portfolio.value if hasattr(portfolio, 'value') else portfolio.net_liquidation_value
    
    # Calculate the weighted sum of strategy CVaRs
    # In a real implementation, this would account for correlations between strategies
    for strategy in portfolio.strategies:
        # Get the strategy value
        strategy_value = strategy.value if hasattr(strategy, 'value') else 0
        
        # Get the strategy weight in the portfolio
        strategy_weight = strategy_value / portfolio_value if portfolio_value > 0 else 0
        
        # Get the strategy CVaR
        strategy_cvar = 0.0
        if hasattr(strategy, 'risk_profile') and hasattr(strategy.risk_profile, 'CVaR'):
            strategy_cvar = strategy.risk_profile.CVaR
        
        # Add the weighted strategy CVaR to the portfolio CVaR
        portfolio_cvar += strategy_weight * strategy_cvar
    
    # Apply a diversification benefit
    # In a real implementation, this would be calculated based on correlations
    diversification_benefit = 0.85  # Assume 15% diversification benefit
    portfolio_cvar *= diversification_benefit
    
    return portfolio_cvar


def get_market_data_for_strategy(strategy):
    """
    This function is now imported from services.market_data
    It's kept here as a wrapper for backward compatibility
    """
    from services.market_data import get_market_data_for_strategy as get_market_data
    return get_market_data(strategy)


def simulate_strategy_pnl(strategy):
    """
    Simulate P&L for a strategy when market data is not available.
    This is a fallback method used for testing or when data providers are unavailable.
    """
    if not strategy.legs:
        return 0.0
    
    # Estimate current value based on greeks and market movement
    days_to_expiry = 30  # Default assumption
    if strategy.legs and strategy.legs[0].expiry:
        try:
            expiry_date = datetime.strptime(strategy.legs[0].expiry, "%Y-%m-%d")
            current_date = datetime.strptime(strategy.date, "%Y-%m-%d")
            days_to_expiry = max(0, (expiry_date - current_date).days)
        except:
            pass
    
    # Simplified P&L calculation based on strategy type and assumptions
    if strategy.assumptions.underlying_direction == "long":
        # For bullish strategies, assume positive P&L if delta is positive
        direction_factor = 1.0
    elif strategy.assumptions.underlying_direction == "short":
        # For bearish strategies, assume positive P&L if delta is negative
        direction_factor = -1.0
    else:
        # For neutral strategies, assume theta decay is primary driver
        direction_factor = 0.0
    
    # Calculate P&L components
    delta_pnl = sum(leg.greeks.delta * leg.cost_basis * direction_factor for leg in strategy.legs)
    theta_pnl = sum(leg.greeks.theta * min(days_to_expiry, 7) for leg in strategy.legs)  # Theta for up to a week
    
    # Total P&L is a combination of delta and theta effects
    total_pnl = delta_pnl + theta_pnl
    
    # For defined risk strategies, cap the profit at a reasonable multiple of premium
    if strategy.risk_profile.risk_category == "defined":
        max_profit = abs(strategy.premium) * 2  # Cap at 2x premium for defined risk
        return max(min(total_pnl, max_profit), -abs(strategy.premium))
    
    return total_pnl


def calculate_survival_probabilities(strategy, expected_daily_move, days=30):
    """
    Calculate the probability that the strategy hits profit targets before hitting max loss.
    
    Returns:
    - Tuple of probabilities (10% profit, 25% profit, 50% profit)
    """
    # In a real implementation, this would use Monte Carlo simulation
    # For demonstration, we'll use a simplified approach based on strategy characteristics
    
    # Default probabilities
    prob_10 = 0.5  # 50% chance of hitting 10% profit
    prob_25 = 0.3  # 30% chance of hitting 25% profit
    prob_50 = 0.1  # 10% chance of hitting 50% profit
    
    # Adjust based on strategy type
    if strategy.risk_profile.risk_category == "defined":
        # Defined risk strategies have higher probability of small profits
        if strategy.assumptions.underlying_direction == "neutral":
            # Neutral strategies (like iron condors) have good chance of small profits
            prob_10 = 0.7
            prob_25 = 0.4
            prob_50 = 0.15
        else:
            # Directional defined risk (like verticals) have medium chance
            prob_10 = 0.6
            prob_25 = 0.35
            prob_50 = 0.12
    else:
        # Undefined risk strategies have lower probability of small profits but higher of large
        if strategy.assumptions.underlying_direction == "neutral":
            # Neutral undefined risk (like strangles) have medium chance
            prob_10 = 0.65
            prob_25 = 0.45
            prob_50 = 0.25
        else:
            # Directional undefined risk have lower chance
            prob_10 = 0.55
            prob_25 = 0.35
            prob_50 = 0.20
    
    # Adjust based on current greeks
    total_delta = sum(leg.greeks.delta for leg in strategy.legs)
    total_gamma = sum(leg.greeks.gamma for leg in strategy.legs)
    total_theta = sum(leg.greeks.theta for leg in strategy.legs)
    
    # Positive theta is good for probability
    theta_factor = min(1.5, max(0.5, 1.0 + (total_theta / 100.0)))
    prob_10 *= theta_factor
    prob_25 *= theta_factor
    prob_50 *= theta_factor
    
    # High gamma can increase probability of hitting larger targets
    gamma_factor = min(1.3, max(0.7, 1.0 + (total_gamma / 50.0)))
    prob_25 *= gamma_factor
    prob_50 *= gamma_factor * 1.1
    
    # Cap probabilities at reasonable values
    prob_10 = min(0.95, max(0.05, prob_10))
    prob_25 = min(0.8, max(0.03, prob_25))
    prob_50 = min(0.6, max(0.01, prob_50))
    
    # Ensure probabilities are decreasing (10% > 25% > 50%)
    prob_25 = min(prob_25, prob_10 * 0.9)
    prob_50 = min(prob_50, prob_25 * 0.8)
    
    return (prob_10, prob_25, prob_50)


def calculate_marginal_contribution_to_risk(portfolio, strategy_cvars, portfolio_cvar):
    """
    Calculate the marginal contribution to risk (MCR) for each strategy in the portfolio.
    
    MCR measures how much each strategy contributes to the overall portfolio risk.
    It's useful for risk budgeting and identifying which strategies are adding the most risk.
    
    This is a simplified implementation that can be replaced with a more sophisticated
    model in the future (e.g., using component VaR or expected shortfall).
    
    Args:
        portfolio: Portfolio object containing strategies
        strategy_cvars: Dictionary of strategy CVaRs
        portfolio_cvar: Total portfolio CVaR
        
    Returns:
        dict: Dictionary of marginal contributions to risk for each strategy
    """
    # Initialize the result dictionary
    mcr_dict = {}
    
    # Calculate the total portfolio value
    portfolio_value = portfolio.value if hasattr(portfolio, 'value') else portfolio.net_liquidation_value
    
    # Calculate the weight of each strategy in the portfolio
    strategy_weights = {}
    for strategy in portfolio.strategies:
        strategy_id = strategy.id
        strategy_value = strategy.value if hasattr(strategy, 'value') else 0
        strategy_weights[strategy_id] = strategy_value / portfolio_value if portfolio_value > 0 else 0
    
    # Calculate the marginal contribution to risk for each strategy
    for strategy in portfolio.strategies:
        strategy_id = strategy.id
        if strategy_id in strategy_cvars and portfolio_cvar > 0:
            # MCR = strategy_weight * strategy_cvar / portfolio_cvar
            # This is a simplified formula that assumes independence between strategies
            # A more sophisticated approach would account for correlations between strategies
            mcr = strategy_weights[strategy_id] * strategy_cvars[strategy_id] / portfolio_cvar
            mcr_dict[strategy_id] = mcr
            
            # Store the MCR in the strategy's risk profile
            strategy.risk_profile.marginal_contribution_to_risk = mcr
        else:
            mcr_dict[strategy_id] = 0
            
            # Store the MCR in the strategy's risk profile
            strategy.risk_profile.marginal_contribution_to_risk = 0
    
    return mcr_dict
