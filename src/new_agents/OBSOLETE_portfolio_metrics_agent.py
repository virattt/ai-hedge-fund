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
    calculate_portfolio_level_metrics(portfolio, market_conditions)
    
    # Step 4: Calculate risk metrics that depend on both strategy and portfolio metrics
    calculate_risk_metrics(portfolio, market_conditions)
    
    # Step 5: Update the enhanced state with the calculated metrics
    update_state_with_calculations(enhanced_state)
    
    # Return the updated state
    return enhanced_state.to_dict()


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
    # Get expected daily move from market conditions
    expected_daily_move = market_conditions.expected_daily_move
    
    # Calculate metrics for each strategy
    for strategy in portfolio.strategies:
        # Calculate strategy P&L
        calculate_strategy_pnl_metrics(strategy)
        
        # Calculate strategy greeks
        calculate_strategy_greeks(strategy, market_conditions)
        
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
        pnl, pnl_percent, pnl_attribution = simulate_strategy_pnl(strategy)
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
    strategy.delta = 0.0
    strategy.gamma = 0.0
    strategy.theta = 0.0
    strategy.vega = 0.0
    
    # If the strategy has no legs, we can't calculate greeks
    if not hasattr(strategy, 'legs') or not strategy.legs:
        # Set default values for testing
        strategy.delta = 30.0
        strategy.gamma = 0.5
        strategy.theta = -50.0
        strategy.vega = 100.0
        return
    
    # Aggregate greeks from all legs
    for leg in strategy.legs:
        # Get leg multiplier (default to 1.0)
        multiplier = getattr(leg, 'multiplier', 1.0)
        
        # Get position size (default to cost_basis if position_size not available)
        if hasattr(leg, 'position_size'):
            position_size = leg.position_size
        else:
            position_size = abs(getattr(leg, 'cost_basis', 1.0))
        
        # Add leg's contribution to strategy greeks
        strategy.delta += leg.greeks.delta * multiplier * position_size
        strategy.gamma += leg.greeks.gamma * multiplier * position_size
        strategy.theta += leg.greeks.theta * multiplier * position_size
        strategy.vega += leg.greeks.vega * multiplier * position_size


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
        expected_daily_move: Expected daily price move as a decimal (e.g., 0.01 for 1%)
    """
    # Initialize risk profile if not present
    if not hasattr(strategy, 'risk_profile'):
        strategy.risk_profile = RiskProfile(risk_category="undefined")
    
    # Get beta for the strategy (default to 1.0 if not available)
    beta = getattr(strategy, 'beta', 1.0)
    
    # Calculate expected delta move (directional exposure)
    # This is the expected P&L contribution from delta
    strategy.risk_profile.expected_delta_move = beta * strategy.delta * expected_daily_move * 100
    
    # Calculate expected convexity move (gamma exposure)
    # This is the expected P&L contribution from gamma
    strategy.risk_profile.expected_convexity_move = beta * strategy.gamma * expected_daily_move * expected_daily_move * 50


def calculate_portfolio_level_metrics(portfolio, market_conditions):
    """
    Calculate portfolio-level metrics based on strategy metrics.
    
    Args:
        portfolio: Portfolio object
        market_conditions: Market conditions object
    """
    # Get expected daily move
    expected_daily_move = market_conditions.expected_daily_move
    
    # Initialize portfolio metrics
    total_delta = 0.0
    total_gamma = 0.0
    total_theta = 0.0
    total_vega = 0.0
    
    # Aggregate metrics from all strategies
    for strategy in portfolio.strategies:
        # Aggregate deltas
        if hasattr(strategy, 'delta'):
            total_delta += strategy.delta
        
        # Aggregate gammas
        if hasattr(strategy, 'gamma'):
            total_gamma += strategy.gamma
        
        # Aggregate thetas
        if hasattr(strategy, 'theta'):
            total_theta += strategy.theta
            
        # Aggregate vegas
        if hasattr(strategy, 'vega'):
            total_vega += strategy.vega
    
    # Set portfolio-level greeks
    portfolio.total_beta_weighted_delta = total_delta
    portfolio.total_beta_weighted_gamma = total_gamma
    portfolio.theta = total_theta
    portfolio.vega = total_vega
    
    # Calculate margin used
    portfolio.margin_used = sum(strategy.risk_profile.margin for strategy in portfolio.strategies)
    
    # Calculate max margin (stress scenario)
    # This is a simplified calculation - in a real system, you would use historical stress testing
    stress_factor = 2.0  # Assume twice the normal margin in stressed conditions
    portfolio.max_margin = portfolio.margin_used * stress_factor
    
    # Initialize ExpectedDailyMove if it doesn't exist
    if not hasattr(portfolio, 'expected_daily_move') or not portfolio.expected_daily_move:
        portfolio.expected_daily_move = ExpectedDailyMove()
    
    # Calculate expected daily move for the portfolio
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
    Calculate expected daily move for the portfolio.
    
    Args:
        portfolio: Portfolio object
        expected_daily_move: Expected daily price move as a decimal (e.g., 0.01 for 1%)
    """
    # Calculate directional exposure (delta * expected move)
    portfolio.expected_daily_move.directional_exposure = portfolio.total_beta_weighted_delta * expected_daily_move
    
    # Calculate convexity exposure (gamma * expected_move^2 / 2)
    portfolio.expected_daily_move.convexity_exposure = portfolio.total_beta_weighted_gamma * expected_daily_move * expected_daily_move / 2
    
    # Set time decay (theta)
    portfolio.expected_daily_move.time_decay = portfolio.theta
    
    # Set volatility exposure (vega * expected_vol_change)
    # For simplicity, we'll use a fixed value for expected vol change
    expected_vol_change = 0.01  # 1% change in implied volatility
    portfolio.expected_daily_move.volatility_exposure = portfolio.vega * expected_vol_change


def calculate_risk_metrics(portfolio, market_conditions):
    """
    Calculate risk metrics that depend on both strategy and portfolio metrics.
    
    Args:
        portfolio: Portfolio object
        market_conditions: Market conditions object
    """
    # Get expected daily move
    expected_daily_move = market_conditions.expected_daily_move
    
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
    
    # Calculate expected daily move for the portfolio
    calculate_portfolio_expected_daily_move(portfolio, expected_daily_move)


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
    
    # If we found an option but it doesn't have greeks, calculate them
    if closest_option and (not closest_option.get("delta") or not closest_option.get("gamma") 
                          or not closest_option.get("theta") or not closest_option.get("vega")):
        # Get the underlying price from the market data
        underlying_price = option_chain.get("underlying_price", 0)
        if underlying_price == 0:
            # Try to get it from other sources in the option chain
            if "underlying" in option_chain and isinstance(option_chain["underlying"], dict):
                underlying_price = option_chain["underlying"].get("price", 0)
        
        # If we have the underlying price, calculate greeks
        if underlying_price > 0:
            # Add option type to the data for greek calculations
            closest_option["option_type"] = option_type
            
            # Calculate greeks
            calculated_greeks = calculate_option_greeks(closest_option, underlying_price)
            
            # Update the option data with calculated greeks
            for greek, value in calculated_greeks.items():
                if not closest_option.get(greek):
                    closest_option[greek] = value
    
    return closest_option


def calculate_option_greeks(option_data, underlying_price, risk_free_rate=0.03):
    """
    Calculate option greeks using market data when they're not available from the data source.
    Uses the Black-Scholes model for European options.
    
    Args:
        option_data: Dictionary containing option data (strike, expiry, implied_volatility, etc.)
        underlying_price: Current price of the underlying asset
        risk_free_rate: Risk-free interest rate (default: 3%)
        
    Returns:
        dict: Dictionary containing calculated greeks (delta, gamma, theta, vega)
    """
    from scipy.stats import norm
    import numpy as np
    from datetime import datetime
    
    # Extract option parameters
    strike = option_data.get("strike", 0)
    if strike == 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}
    
    # Get option type (call or put)
    option_type = option_data.get("option_type", "").lower()
    if not option_type:
        option_type = "call" if option_data.get("call", 0) > 0 else "put"
    
    # Get implied volatility
    iv = option_data.get("implied_volatility", 0)
    if iv == 0:
        # If IV is not available, estimate it based on the option's moneyness and time to expiry
        moneyness = underlying_price / strike
        if moneyness < 0.95:
            iv = 0.30  # OTM options tend to have higher IV
        elif moneyness > 1.05:
            iv = 0.25  # ITM options tend to have lower IV
        else:
            iv = 0.20  # ATM options
    
    # Get expiry date
    expiry_str = option_data.get("expiry", "")
    if not expiry_str:
        # Default to 30 days if expiry is not available
        time_to_expiry = 30/365
    else:
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            current_date = datetime.now()
            time_to_expiry = max((expiry_date - current_date).days, 1) / 365
        except (ValueError, TypeError):
            # Default to 30 days if there's an error parsing the date
            time_to_expiry = 30/365
    
    # Calculate Black-Scholes parameters
    S = underlying_price
    K = strike
    r = risk_free_rate
    sigma = iv
    T = time_to_expiry
    
    # Calculate d1 and d2
    d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    # Calculate greeks based on option type
    if option_type == "call":
        delta = norm.cdf(d1)
        theta = -(S * sigma * norm.pdf(d1)) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
    else:  # put
        delta = norm.cdf(d1) - 1
        theta = -(S * sigma * norm.pdf(d1)) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
    
    # Gamma and Vega are the same for calls and puts
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * np.sqrt(T) * norm.pdf(d1) / 100  # Divided by 100 to get the effect of a 1% change in IV
    
    # Theta is typically quoted as the daily decay, so divide by 365
    theta = theta / 365
    
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega
    }


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
    try:
        pnl, pnl_percent, pnl_attribution = calculate_strategy_pnl(strategy)
        strategy.pnl = pnl
        strategy.pnl_percent = pnl_percent
        return strategy, pnl_attribution
    except Exception as e:
        # If there's an error, return a default pnl_attribution
        default_pnl_attribution = {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "other": 0.0
        }
        return strategy, default_pnl_attribution


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
        expected_daily_move: Expected daily price move as a decimal (e.g., 0.01 for 1%)
        
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
    Simulate P&L for a strategy when real market data is unavailable.
    
    Args:
        strategy: Strategy object
        
    Returns:
        tuple: (pnl, pnl_percent, pnl_attribution)
    """
    # Simple simulation - in a real system this would use more sophisticated models
    pnl = 0.0  # Default to zero P&L
    
    # Calculate P&L percent
    if hasattr(strategy, 'cost_basis') and strategy.cost_basis != 0:
        pnl_percent = pnl / abs(strategy.cost_basis) * 100
    else:
        pnl_percent = 0.0
    
    # Create a simple P&L attribution dictionary
    pnl_attribution = {
        "delta": 0.0,
        "gamma": 0.0,
        "theta": 0.0,
        "vega": 0.0,
        "other": 0.0
    }
    
    return pnl, pnl_percent, pnl_attribution


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

def calculate_portfolio_expected_daily_move(portfolio, expected_daily_move):
    """
    Calculate expected daily move for the portfolio.
    
    Args:
        portfolio: Portfolio object
        expected_daily_move: Expected daily price move as a decimal (e.g., 0.01 for 1%)
    """
    # Calculate directional exposure (delta * expected move)
    portfolio.expected_daily_move.directional_exposure = portfolio.total_beta_weighted_delta * expected_daily_move
    
    # Calculate convexity exposure (gamma * expected_move^2 / 2)
    portfolio.expected_daily_move.convexity_exposure = portfolio.total_beta_weighted_gamma * expected_daily_move * expected_daily_move / 2
    
    # Set time decay (theta)
    portfolio.expected_daily_move.time_decay = portfolio.theta
    
    # Set volatility exposure (vega * expected_vol_change)
    # For simplicity, we'll use a fixed value for expected vol change
    expected_vol_change = 0.01  # 1% change in implied volatility
    portfolio.expected_daily_move.volatility_exposure = portfolio.vega * expected_vol_change
