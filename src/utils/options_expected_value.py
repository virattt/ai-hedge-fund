import numpy as np
from scipy.stats import norm
import math
from datetime import datetime
from typing import List, Dict, Tuple, Any
from new_graph.state import AgentState

def black_scholes(S, K, T, r, sigma, option_type='call'):
    """
    Calculate option price using Black-Scholes model
    
    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility
        option_type: 'call' or 'put'
        
    Returns:
        Option price and greeks (delta, gamma, theta, vega)
    """
    if T <= 0:
        if option_type == 'call':
            return max(0, S - K), 0, 0, 0, 0, 1.0 if S > K else 0.0
        else:
            return max(0, K - S), 0, 0, 0, 0, 1.0 if K > S else 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        itm_probability = norm.cdf(d2)  # Probability of finishing in-the-money
    else:  # put
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = -norm.cdf(-d1)
        itm_probability = norm.cdf(-d2)  # Probability of finishing in-the-money
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    theta = -(S * sigma * norm.pdf(d1)) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2) if option_type == 'call' else \
            -(S * sigma * norm.pdf(d1)) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
    vega = S * np.sqrt(T) * norm.pdf(d1)
    
    return price, delta, gamma, theta, vega, itm_probability


def calculate_option_payoff(stock_price, strike, option_type, position):
    """
    Calculate option payoff at expiration
    
    Args:
        stock_price: Stock price at expiration
        strike: Option strike price
        option_type: 'call' or 'put'
        position: 1 for long, -1 for short
        
    Returns:
        Option payoff
    """
    if option_type == 'call':
        return position * max(0, stock_price - strike)
    else:  # put
        return position * max(0, strike - stock_price)


def calculate_strategy_payoff(stock_price, legs):
    """
    Calculate total strategy payoff for a given stock price
    
    Args:
        stock_price: Stock price at expiration
        legs: List of option legs in the strategy
        
    Returns:
        Total strategy payoff
    """
    total_payoff = 0
    
    for leg in legs:
        option_type = 'call' if leg.call != 0 else 'put'
        position = leg.call if leg.call != 0 else leg.put
        multiplier = leg.multiplier if hasattr(leg, 'multiplier') else 100
        
        # Calculate payoff for this leg
        leg_payoff = calculate_option_payoff(stock_price, leg.strike, option_type, position)
        
        # Apply multiplier and add to total
        total_payoff += leg_payoff * multiplier
    
    return total_payoff


def calculate_breakeven_points(strategy):
    """
    Calculate breakeven points for a strategy
    
    Args:
        strategy: The options strategy
        
    Returns:
        List of breakeven points
    """
    if not hasattr(strategy, 'legs') or not strategy.legs:
        return []
    
    # For standard option strategies, breakeven points can be calculated analytically
    # based on strike prices and premium
    
    # Get premium (positive for credit, negative for debit)
    premium = strategy.premium
    
    # Identify strategy type based on legs
    legs = strategy.legs
    
    # Check if this is a single option
    if len(legs) == 1:
        leg = legs[0]
        strike = leg.strike
        
        if leg.call > 0:  # Long call
            # Breakeven = strike + premium/multiplier
            multiplier = leg.multiplier if hasattr(leg, 'multiplier') else 100
            return [strike + abs(premium) / multiplier]
        elif leg.call < 0:  # Short call
            # Breakeven = strike + premium/multiplier
            multiplier = leg.multiplier if hasattr(leg, 'multiplier') else 100
            return [strike + premium / multiplier]
        elif leg.put > 0:  # Long put
            # Breakeven = strike - premium/multiplier
            multiplier = leg.multiplier if hasattr(leg, 'multiplier') else 100
            return [strike - abs(premium) / multiplier]
        elif leg.put < 0:  # Short put
            # Breakeven = strike - premium/multiplier
            multiplier = leg.multiplier if hasattr(leg, 'multiplier') else 100
            return [strike - premium / multiplier]
    
    # Check if this is a vertical spread
    elif len(legs) == 2 and ((legs[0].call != 0 and legs[1].call != 0) or (legs[0].put != 0 and legs[1].put != 0)):
        # Sort legs by strike
        sorted_legs = sorted(legs, key=lambda x: x.strike)
        lower_strike = sorted_legs[0].strike
        higher_strike = sorted_legs[1].strike
        multiplier = sorted_legs[0].multiplier if hasattr(sorted_legs[0], 'multiplier') else 100
        
        # Determine if it's a call or put spread
        is_call_spread = sorted_legs[0].call != 0
        
        # Determine if it's a credit or debit spread
        is_credit_spread = premium > 0
        
        if is_call_spread:
            if is_credit_spread:  # Short call spread
                # Breakeven = higher strike - premium/multiplier
                return [higher_strike - premium / multiplier]
            else:  # Long call spread
                # Breakeven = lower strike + abs(premium)/multiplier
                return [lower_strike + abs(premium) / multiplier]
        else:  # Put spread
            if is_credit_spread:  # Short put spread
                # Breakeven = lower strike + premium/multiplier
                return [lower_strike + premium / multiplier]
            else:  # Long put spread
                # Breakeven = higher strike - abs(premium)/multiplier
                return [higher_strike - abs(premium) / multiplier]
    
    # Check if this is an iron condor or iron butterfly
    elif len(legs) == 4:
        # Sort legs by strike
        sorted_legs = sorted(legs, key=lambda x: x.strike)
        strikes = [leg.strike for leg in sorted_legs]
        
        # Check if we have 2 unique strikes (iron butterfly) or 4 (iron condor)
        unique_strikes = sorted(list(set(strikes)))
        
        if len(unique_strikes) == 4:  # Iron condor
            multiplier = sorted_legs[0].multiplier if hasattr(sorted_legs[0], 'multiplier') else 100
            # Lower breakeven = lowest strike + premium/multiplier
            # Upper breakeven = highest strike - premium/multiplier
            return [unique_strikes[0] + premium / multiplier, unique_strikes[3] - premium / multiplier]
        elif len(unique_strikes) == 3 and strikes.count(unique_strikes[1]) == 2:  # Broken-wing butterfly
            multiplier = sorted_legs[0].multiplier if hasattr(sorted_legs[0], 'multiplier') else 100
            # This is more complex, would need to know exact structure
            # For simplicity, use numerical method for this case
            return _calculate_breakeven_points_numerical(strategy)
        elif len(unique_strikes) == 2:  # Iron butterfly
            multiplier = sorted_legs[0].multiplier if hasattr(sorted_legs[0], 'multiplier') else 100
            # Lower breakeven = lower strike + premium/multiplier
            # Upper breakeven = higher strike - premium/multiplier
            return [unique_strikes[0] + premium / multiplier, unique_strikes[1] - premium / multiplier]
    
    # For more complex strategies, fall back to numerical method
    return _calculate_breakeven_points_numerical(strategy)


def _calculate_breakeven_points_numerical(strategy):
    """
    Calculate breakeven points using numerical approximation for complex strategies
    
    Args:
        strategy: The options strategy
        
    Returns:
        List of breakeven points
    """
    # Get current stock price
    if hasattr(strategy, 'legs') and strategy.legs:
        current_price = strategy.legs[0].stock_price if hasattr(strategy.legs[0], 'stock_price') else 0
    else:
        return []
    
    # Sample range of potential stock prices at expiration
    price_range = np.linspace(current_price * 0.5, current_price * 1.5, 1000)
    payoffs = [calculate_strategy_payoff(price, strategy.legs) - strategy.premium for price in price_range]
    
    # Find where payoff crosses zero (breakeven points)
    breakevens = []
    for i in range(1, len(payoffs)):
        if payoffs[i-1] * payoffs[i] <= 0:  # Sign change indicates crossing zero
            # Linear interpolation to find more precise breakeven
            x1, x2 = price_range[i-1], price_range[i]
            y1, y2 = payoffs[i-1], payoffs[i]
            
            if y1 == y2:  # Avoid division by zero
                breakeven = (x1 + x2) / 2
            else:
                breakeven = x1 - y1 * (x2 - x1) / (y2 - y1)
            
            breakevens.append(breakeven)
    
    return breakevens


def identify_profit_zones(strategy):
    """
    Identify profit zones for a strategy based on breakeven points
    
    Args:
        strategy: The options strategy
        
    Returns:
        Dictionary with profit zones and their characteristics
    """
    # Calculate breakeven points
    breakeven_points = calculate_breakeven_points(strategy)
    
    if not breakeven_points:
        return {"type": "unknown", "breakevens": []}
    
    # Get a reference price to test payoffs
    if hasattr(strategy, 'legs') and strategy.legs:
        current_price = strategy.legs[0].stock_price if hasattr(strategy.legs[0], 'stock_price') else 0
    else:
        return {"type": "unknown", "breakevens": []}
    
    # Sort breakeven points
    breakeven_points.sort()
    
    # Test points to determine profit zones
    test_points = []
    
    # For single breakeven
    if len(breakeven_points) == 1:
        breakeven = breakeven_points[0]
        # Test points below and above breakeven
        test_points = [breakeven * 0.5, breakeven * 1.5]
    
    # For two breakevens
    elif len(breakeven_points) == 2:
        lower_breakeven = breakeven_points[0]
        upper_breakeven = breakeven_points[1]
        # Test points below, between, and above breakevens
        test_points = [lower_breakeven * 0.5, (lower_breakeven + upper_breakeven) / 2, upper_breakeven * 1.5]
    
    # For more breakevens (rare but possible)
    else:
        # Create test points between each pair of breakevens and beyond
        test_points.append(breakeven_points[0] * 0.5)  # Below first breakeven
        for i in range(len(breakeven_points) - 1):
            test_points.append((breakeven_points[i] + breakeven_points[i+1]) / 2)  # Between breakevens
        test_points.append(breakeven_points[-1] * 1.5)  # Above last breakeven
    
    # Calculate payoffs at test points
    payoffs = []
    for price in test_points:
        payoff = calculate_strategy_payoff(price, strategy.legs) - strategy.premium
        payoffs.append(payoff > 0)  # True if profitable
    
    # Determine profit zone type based on payoffs
    result = {
        "breakevens": breakeven_points,
        "payoffs": list(zip(test_points, payoffs))
    }
    
    # Single breakeven
    if len(breakeven_points) == 1:
        if payoffs[0] and not payoffs[1]:  # Profitable below breakeven
            result["type"] = "below"
            result["profit_below"] = True
        elif not payoffs[0] and payoffs[1]:  # Profitable above breakeven
            result["type"] = "above"
            result["profit_below"] = False
        else:
            result["type"] = "unknown"
    
    # Two breakevens
    elif len(breakeven_points) == 2:
        if not payoffs[0] and payoffs[1] and not payoffs[2]:  # Profitable between breakevens
            result["type"] = "between"
            result["profit_between"] = True
        elif payoffs[0] and not payoffs[1] and payoffs[2]:  # Profitable outside breakevens
            result["type"] = "outside"
            result["profit_between"] = False
        else:
            result["type"] = "complex"
    
    # More complex cases
    else:
        result["type"] = "complex"
    
    return result


def calculate_probability_of_profit(strategy, risk_free_rate):
    """
    Calculate probability of profit using Black-Scholes model
    
    Args:
        strategy: The options strategy
        risk_free_rate: Risk-free interest rate
        
    Returns:
        Probability of profit
    """
    if not hasattr(strategy, 'legs') or not strategy.legs:
        return 0.0
    
    # Get current stock price and days to expiration from first leg
    first_leg = strategy.legs[0]
    current_price = first_leg.stock_price if hasattr(first_leg, 'stock_price') else 0
    
    # Calculate time to expiration in years
    dte = 0
    if hasattr(first_leg, "DTE"):
        dte = first_leg.DTE
    elif hasattr(first_leg, "expiry"):
        try:
            expiry_date = datetime.strptime(first_leg.expiry, "%Y-%m-%d")
            today = datetime.now()
            dte = max(0, (expiry_date - today).days)
        except (ValueError, TypeError):
            dte = 0
    
    T = dte / 365.0  # Convert days to years
    
    # If expired or no price data, return default values
    if T <= 0 or current_price <= 0:
        return 0.0
    
    # Get implied volatility from first leg
    iv = first_leg.greeks.iv if hasattr(first_leg, 'greeks') and hasattr(first_leg.greeks, 'iv') else 0.3
    
    # Identify profit zones
    profit_zones = identify_profit_zones(strategy)
    
    # If we couldn't determine profit zones, return default
    if profit_zones["type"] == "unknown":
        return 0.5
    
    # Calculate probability based on profit zone type
    if profit_zones["type"] == "below":
        # Need price to stay below the breakeven
        breakeven = profit_zones["breakevens"][0]
        # Calculate d1 and d2 for Black-Scholes
        d1 = (np.log(current_price / breakeven) + (risk_free_rate + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
        d2 = d1 - iv * np.sqrt(T)  # d2 is used for probability calculation
        return norm.cdf(-d2)  # Use d2 for probability calculation
    
    elif profit_zones["type"] == "above":
        # Need price to go above the breakeven
        breakeven = profit_zones["breakevens"][0]
        # Calculate d1 and d2 for Black-Scholes
        d1 = (np.log(current_price / breakeven) + (risk_free_rate + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
        d2 = d1 - iv * np.sqrt(T)  # d2 is used for probability calculation
        return norm.cdf(d2)  # Use d2 for probability calculation
    
    elif profit_zones["type"] == "between":
        # Need price to stay between the breakevens
        lower_breakeven = profit_zones["breakevens"][0]
        upper_breakeven = profit_zones["breakevens"][1]
        
        # Calculate d1 and d2 for lower breakeven
        d1_lower = (np.log(current_price / lower_breakeven) + (risk_free_rate + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
        d2_lower = d1_lower - iv * np.sqrt(T)
        
        # Calculate d1 and d2 for upper breakeven
        d1_upper = (np.log(current_price / upper_breakeven) + (risk_free_rate + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
        d2_upper = d1_upper - iv * np.sqrt(T)
        
        # Probability is the difference between the two CDFs
        return norm.cdf(d2_lower) - norm.cdf(d2_upper)
    
    elif profit_zones["type"] == "outside":
        # Need price to be outside the breakevens
        lower_breakeven = profit_zones["breakevens"][0]
        upper_breakeven = profit_zones["breakevens"][1]
        
        # Calculate d1 and d2 for lower breakeven
        d1_lower = (np.log(current_price / lower_breakeven) + (risk_free_rate + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
        d2_lower = d1_lower - iv * np.sqrt(T)
        
        # Calculate d1 and d2 for upper breakeven
        d1_upper = (np.log(current_price / upper_breakeven) + (risk_free_rate + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
        d2_upper = d1_upper - iv * np.sqrt(T)
        
        # Probability is 1 minus the probability of being between breakevens
        return 1 - (norm.cdf(d2_lower) - norm.cdf(d2_upper))
    
    # For complex profit zones, we would need a more sophisticated approach
    # For now, default to a 50% probability
    return 0.5


def calculate_expected_value_analytical(strategy, risk_free_rate):
    """
    Calculate expected value using analytical approach
    
    Args:
        strategy: The options strategy
        risk_free_rate: Risk-free interest rate
        
    Returns:
        Expected value of the strategy
    """
    if not hasattr(strategy, 'legs') or not strategy.legs:
        return 0.0
    
    # Get current stock price and days to expiration from first leg
    first_leg = strategy.legs[0]
    current_price = first_leg.stock_price if hasattr(first_leg, 'stock_price') else 0
    
    # Calculate time to expiration in years
    dte = 0
    if hasattr(first_leg, "DTE"):
        dte = first_leg.DTE
    elif hasattr(first_leg, "expiry"):
        try:
            expiry_date = datetime.strptime(first_leg.expiry, "%Y-%m-%d")
            today = datetime.now()
            dte = max(0, (expiry_date - today).days)
        except (ValueError, TypeError):
            dte = 0
    
    T = dte / 365.0  # Convert days to years
    
    # If expired or no price data, return default values
    if T <= 0 or current_price <= 0:
        return 0.0
    
    # Get implied volatility from first leg
    iv = first_leg.greeks.iv if hasattr(first_leg, 'greeks') and hasattr(first_leg.greeks, 'iv') else 0.3
    
    # Calculate theoretical value for each leg using Black-Scholes
    theoretical_value = 0
    
    for leg in strategy.legs:
        option_type = 'call' if leg.call != 0 else 'put'
        position = leg.call if leg.call != 0 else leg.put
        strike = leg.strike
        multiplier = leg.multiplier if hasattr(leg, 'multiplier') else 100
        
        # Calculate option price using Black-Scholes
        price, _, _, _, _, _ = black_scholes(
            S=current_price,
            K=strike,
            T=T,
            r=risk_free_rate,
            sigma=iv,
            option_type=option_type
        )
        
        # Add to theoretical value
        theoretical_value += position * price * multiplier
    
    # Expected value is theoretical value minus premium paid/received
    expected_value = theoretical_value - strategy.premium
    
    return expected_value


def calculate_expected_value(state: AgentState, strategy_index: int) -> Dict[str, Any]:
    """
    Calculate the theoretical expected value of an options strategy
    
    Args:
        state: The agent state containing portfolio and market data
        strategy_index: Index of the strategy to analyze
        
    Returns:
        Dictionary with probability of profit, breakeven points, and expected value
    """
    portfolio = state.data.portfolio
    strategy = portfolio.strategies[strategy_index]
    
    # Extract market data
    risk_free_rate = state.data.market_conditions.risk_free_rate if hasattr(state.data.market_conditions, 'risk_free_rate') else 0.05
    
    # Initialize results
    result = {
        "ticker": strategy.ticker,
        "description": strategy.description,
        "pop": 0.0,
        "breakeven_points": [],
        "expected_value": 0.0,
        "premium": strategy.premium
    }
    
    # Check if strategy has legs
    if not hasattr(strategy, 'legs') or not strategy.legs:
        return result
    
    # Calculate breakeven points
    breakeven_points = calculate_breakeven_points(strategy)
    result["breakeven_points"] = breakeven_points
    
    # Calculate probability of profit using Black-Scholes
    pop = calculate_probability_of_profit(strategy, risk_free_rate)
    result["pop"] = pop
    
    # Calculate expected value using analytical approach
    expected_value = calculate_expected_value_analytical(strategy, risk_free_rate)
    result["expected_value"] = expected_value
    
    return result


def calculate_all_expected_values(state: AgentState) -> Dict[str, Dict[str, Any]]:
    """
    Calculate expected values for all strategies in the portfolio
    
    Args:
        state: The agent state containing portfolio and market data
        
    Returns:
        Dictionary mapping strategy tickers to their expected value analysis
    """
    portfolio = state.data.portfolio
    results = {}
    
    for i, strategy in enumerate(portfolio.strategies):
        ticker = strategy.ticker
        results[ticker] = calculate_expected_value(state, i)
        
        # Update the strategy's risk profile with the calculated values
        strategy.risk_profile.expected_value = results[ticker]["expected_value"]
        strategy.risk_profile.pop = results[ticker]["pop"]
    
    return results
