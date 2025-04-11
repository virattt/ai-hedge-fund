"""
Market Data Service

This module provides centralized market data retrieval and caching for all agents.
It abstracts the data provider implementation and provides a consistent interface
for accessing market data throughout the application.
"""

import os
import pickle
from datetime import datetime, timedelta
from functools import lru_cache
import numpy as np
from scipy.stats import norm
import math
import random

from tools.api import get_prices, prices_to_df
from utils.progress import progress

# Cache directory for market data
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")

# Ensure cache directory exists
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)


class MarketDataCache:
    """
    Cache for market data to avoid unnecessary API calls.
    Implements both memory caching and disk persistence.
    """
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        self.memory_cache = {}
        self.cache_ttl = 24 * 60 * 60  # 24 hours in seconds
        self._load_cache_from_disk()
    
    def _get_cache_file_path(self, date):
        """Get the cache file path for a specific date."""
        return os.path.join(self.cache_dir, f"market_data_{date}.pkl")
    
    def _load_cache_from_disk(self):
        """Load cached data from disk into memory."""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_file = self._get_cache_file_path(today)
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    self.memory_cache = pickle.load(f)
                    progress.update_status("market_data_cache", "load", f"Loaded market data cache for {today}")
            except Exception as e:
                progress.update_status("market_data_cache", "load", f"Error loading cache: {str(e)}")
                self.memory_cache = {}
    
    def _save_cache_to_disk(self):
        """Save the current memory cache to disk."""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_file = self._get_cache_file_path(today)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(self.memory_cache, f)
                progress.update_status("market_data_cache", "save", f"Saved market data cache for {today}")
        except Exception as e:
            progress.update_status("market_data_cache", "save", f"Error saving cache: {str(e)}")
    
    def get(self, key, default=None):
        """Get data from cache if it exists and is not expired."""
        if key in self.memory_cache:
            timestamp, data = self.memory_cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return data
        return default
    
    def set(self, key, data):
        """Store data in cache with current timestamp."""
        self.memory_cache[key] = (datetime.now(), data)
        # Save to disk periodically (could optimize to not save on every set)
        self._save_cache_to_disk()
        return data


# Initialize the market data cache as a singleton
market_data_cache = MarketDataCache()


@lru_cache(maxsize=128)
def get_cached_prices(ticker, start_date, end_date):
    """
    Get cached price data or fetch from API if not available.
    Uses both the MarketDataCache and Python's lru_cache for efficiency.
    
    Args:
        ticker (str): The ticker symbol
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        
    Returns:
        dict: Price data for the ticker
    """
    cache_key = f"prices_{ticker}_{start_date}_{end_date}"
    
    # Check if data is in cache
    cached_data = market_data_cache.get(cache_key)
    if cached_data is not None:
        progress.update_status("market_data_cache", ticker, "Using cached price data")
        return cached_data
    
    # If not in cache, fetch from API
    progress.update_status("market_data_cache", ticker, "Fetching price data from API")
    prices = get_prices(ticker=ticker, start_date=start_date, end_date=end_date)
    
    # Cache the result if successful
    if prices:
        market_data_cache.set(cache_key, prices)
    
    return prices


def get_market_data_for_strategy(strategy):
    """
    Retrieve market data for a strategy.
    Uses caching to avoid unnecessary API calls.
    
    This function returns raw market data that can be used by any agent.
    Specific formatting for P&L or other calculations should be done in the agent.
    
    Args:
        strategy: Strategy object containing ticker and other information
        
    Returns:
        dict: Raw market data for the strategy
    """
    ticker = strategy.ticker
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Create a cache key for this strategy's market data
    cache_key = f"market_data_{ticker}_{current_date}"
    
    # Check if we have cached data
    cached_data = market_data_cache.get(cache_key)
    if cached_data is not None:
        progress.update_status("market_data_service", ticker, "Using cached market data")
        return cached_data
    
    # If not in cache, we need to fetch/generate the data
    progress.update_status("market_data_service", ticker, "Fetching market data")
    
    # Get historical price data for the past 60 days
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    prices = get_cached_prices(ticker, start_date, end_date)
    prices_df = prices_to_df(prices)
    
    if prices_df is not None and not prices_df.empty:
        market_data = {
            "ticker": ticker,
            "date": current_date,
            "underlying": {
                "current_price": float(prices_df["close"].iloc[-1]),
                "previous_price": float(prices_df["close"].iloc[-2]) if len(prices_df) > 1 else float(prices_df["close"].iloc[-1] * 0.99),
                "open": float(prices_df["open"].iloc[-1]),
                "high": float(prices_df["high"].iloc[-1]),
                "low": float(prices_df["low"].iloc[-1]),
                "volume": float(prices_df["volume"].iloc[-1]) if "volume" in prices_df else 1000000,
            },
            "options": {},
            "historical": {}
        }
        
        # Calculate historical volatility
        if len(prices_df) > 5:
            returns = np.log(prices_df["close"] / prices_df["close"].shift(1)).dropna()
            market_data["underlying"]["historical_volatility"] = float(returns.std() * np.sqrt(252))
        
        # For options data, fetch the option chain with current market prices
        option_chain = get_option_chain(ticker, current_date)
        if option_chain:
            market_data["options"] = option_chain
        
        # Get market indicators (SPX, VIX, etc.)
        market_indicators = get_market_indicators(current_date)
        if market_indicators:
            market_data["market_indicators"] = market_indicators
        
        # Cache the market data
        market_data_cache.set(cache_key, market_data)
        
        return market_data
    
    else:
        return None


def get_option_chain(ticker, date=None):
    """
    Get option chain data for a ticker.
    
    Args:
        ticker (str): The ticker symbol
        date (str, optional): Date in YYYY-MM-DD format. Defaults to current date.
        
    Returns:
        dict: Raw option chain data
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    cache_key = f"option_chain_{ticker}_{date}"
    
    # Check if data is in cache
    cached_data = market_data_cache.get(cache_key)
    if cached_data is not None:
        progress.update_status("market_data_service", ticker, "Using cached option chain data")
        return cached_data
    
    # If not in cache, we would fetch from API
    # For now, return a placeholder with a realistic structure
    progress.update_status("market_data_service", ticker, "Fetching option chain data")
    
    # Get the current price (or estimate)
    current_price = 0
    try:
        start_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        prices = get_cached_prices(ticker=ticker, start_date=start_date, end_date=date)
        if prices:
            prices_df = prices_to_df(prices)
            current_price = float(prices_df["close"].iloc[-1])
    except:
        # If we can't get the price, use a placeholder
        current_price = 100.0
    
    # Generate realistic option chain data
    option_chain = generate_realistic_option_chain(ticker, current_price, date)
    
    # Cache the result
    market_data_cache.set(cache_key, option_chain)
    
    return option_chain


def generate_realistic_option_chain(ticker, current_price, date):
    """
    Generate a realistic option chain based on the current price.
    
    Args:
        ticker (str): The ticker symbol
        current_price (float): Current price of the underlying
        date (str): Current date in YYYY-MM-DD format
        
    Returns:
        dict: Realistic option chain data
    """
    # Create expiration dates (weekly, monthly, quarterly)
    current_date = datetime.strptime(date, "%Y-%m-%d")
    
    # Generate expiration dates (next 4 weeklies, next 3 monthlies, next 2 quarterlies)
    expiry_dates = []
    
    # Weekly expirations (next 4 Fridays)
    for i in range(1, 5):
        # Find the next Friday
        days_until_friday = (4 - current_date.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        friday = current_date + timedelta(days=days_until_friday + (i-1)*7)
        expiry_dates.append(friday.strftime("%Y-%m-%d"))
    
    # Monthly expirations (third Friday of next 3 months)
    for i in range(1, 4):
        next_month = current_date.replace(day=1) + timedelta(days=32*i)
        next_month = next_month.replace(day=1)
        # Find the third Friday
        days_until_friday = (4 - next_month.weekday()) % 7
        third_friday = next_month + timedelta(days=days_until_friday + 14)
        expiry_dates.append(third_friday.strftime("%Y-%m-%d"))
    
    # Quarterly expirations (third Friday of the quarter month)
    for i in range(1, 3):
        # Find next quarter month
        month = current_date.month
        quarter_month = 3 * ((month - 1) // 3 + i)
        if quarter_month > 12:
            quarter_month = quarter_month - 12
            year = current_date.year + 1
        else:
            year = current_date.year
        
        quarter_date = datetime(year, quarter_month, 1)
        # Find the third Friday
        days_until_friday = (4 - quarter_date.weekday()) % 7
        third_friday = quarter_date + timedelta(days=days_until_friday + 14)
        expiry_dates.append(third_friday.strftime("%Y-%m-%d"))
    
    # Remove duplicates and sort
    expiry_dates = sorted(list(set(expiry_dates)))
    
    # Generate strikes around the current price (realistic strike spacing)
    strike_spacing = get_strike_spacing(current_price)
    num_strikes = 15  # Number of strikes above and below current price
    
    atm_strike = round(current_price / strike_spacing) * strike_spacing
    strikes = [round(atm_strike + i * strike_spacing, 2) for i in range(-num_strikes, num_strikes + 1)]
    
    # Generate option data
    option_chain = {
        "underlying_price": current_price,
        "timestamp": datetime.now().isoformat(),
        "expiration_dates": expiry_dates,
        "strikes": strikes,
        "calls": [],
        "puts": []
    }
    
    # Get VIX for implied volatility baseline
    vix = 20.0  # Default value
    market_indicators = get_market_indicators(date)
    if market_indicators and "vix" in market_indicators:
        vix = market_indicators["vix"]
    
    # Generate option data for each expiration and strike
    for expiry in expiry_dates:
        expiry_key = expiry.replace("-", "")
        
        # Calculate days to expiry
        days_to_expiry = (datetime.strptime(expiry, "%Y-%m-%d") - current_date).days
        
        # Base implied volatility (higher for longer-dated options)
        base_iv = vix / 100 * (1 + 0.05 * (days_to_expiry / 30))
        
        for strike in strikes:
            # Calculate moneyness
            moneyness = strike / current_price - 1
            
            # Adjust IV for strike (volatility smile)
            call_iv = base_iv * (1 + 0.2 * abs(moneyness))
            put_iv = base_iv * (1 + 0.2 * abs(moneyness))
            
            # Calculate option prices using Black-Scholes approximation
            call_price = black_scholes_approx(current_price, strike, days_to_expiry/365, 0.03, call_iv, True)
            put_price = black_scholes_approx(current_price, strike, days_to_expiry/365, 0.03, put_iv, False)
            
            # Calculate Greeks
            call_delta = calculate_delta(current_price, strike, days_to_expiry/365, 0.03, call_iv, True)
            put_delta = calculate_delta(current_price, strike, days_to_expiry/365, 0.03, put_iv, False)
            
            call_gamma = calculate_gamma(current_price, strike, days_to_expiry/365, 0.03, call_iv)
            put_gamma = call_gamma  # Gamma is the same for calls and puts
            
            call_theta = calculate_theta(current_price, strike, days_to_expiry/365, 0.03, call_iv, True)
            put_theta = calculate_theta(current_price, strike, days_to_expiry/365, 0.03, put_iv, False)
            
            call_vega = calculate_vega(current_price, strike, days_to_expiry/365, 0.03, call_iv)
            put_vega = call_vega  # Vega is the same for calls and puts
            
            # Add call option
            option_chain["calls"].append({
                "strike": strike,
                "expiry": expiry,
                "bid": round(call_price * 0.95, 2),
                "ask": round(call_price * 1.05, 2),
                "last": round(call_price, 2),
                "volume": int(np.random.lognormal(5, 1)),
                "open_interest": int(np.random.lognormal(6, 1.5)),
                "implied_volatility": round(call_iv, 4),
                "delta": round(call_delta, 4),
                "gamma": round(call_gamma, 4),
                "theta": round(call_theta, 4),
                "vega": round(call_vega, 4)
            })
            
            # Add put option
            option_chain["puts"].append({
                "strike": strike,
                "expiry": expiry,
                "bid": round(put_price * 0.95, 2),
                "ask": round(put_price * 1.05, 2),
                "last": round(put_price, 2),
                "volume": int(np.random.lognormal(5, 1)),
                "open_interest": int(np.random.lognormal(6, 1.5)),
                "implied_volatility": round(put_iv, 4),
                "delta": round(put_delta, 4),
                "gamma": round(put_gamma, 4),
                "theta": round(put_theta, 4),
                "vega": round(put_vega, 4)
            })
    
    return option_chain


def get_strike_spacing(price):
    """
    Get appropriate strike spacing based on the underlying price.
    
    Args:
        price (float): Current price of the underlying
        
    Returns:
        float: Appropriate strike spacing
    """
    if price < 5:
        return 0.5
    elif price < 25:
        return 1.0
    elif price < 100:
        return 2.5
    elif price < 250:
        return 5.0
    else:
        return 10.0


def norm_cdf(x):
    """Approximation of the normal CDF function."""
    return norm.cdf(x)


def norm_pdf(x):
    """Approximation of the normal PDF function."""
    return norm.pdf(x)


def black_scholes_approx(S, K, T, r, sigma, is_call):
    """
    Calculate option price using Black-Scholes approximation.
    
    Args:
        S (float): Underlying price
        K (float): Strike price
        T (float): Time to expiry in years
        r (float): Risk-free rate
        sigma (float): Implied volatility
        is_call (bool): True for call option, False for put option
        
    Returns:
        float: Option price
    """
    if T <= 0:
        # Handle expired options
        if is_call:
            return max(0, S - K)
        else:
            return max(0, K - S)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if is_call:
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    
    return price


def calculate_delta(S, K, T, r, sigma, is_call):
    """Calculate option delta."""
    if T <= 0:
        return 1.0 if is_call and S > K else 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    
    if is_call:
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1


def calculate_gamma(S, K, T, r, sigma):
    """Calculate option gamma."""
    if T <= 0:
        return 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))


def calculate_theta(S, K, T, r, sigma, is_call):
    """Calculate option theta."""
    if T <= 0:
        return 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if is_call:
        theta = -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
    else:
        theta = -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
    
    return theta / 365  # Convert to daily theta


def calculate_vega(S, K, T, r, sigma):
    """Calculate option vega."""
    if T <= 0:
        return 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return S * np.sqrt(T) * norm.pdf(d1) / 100  # Divide by 100 to get vega per 1% change in IV


def get_market_indicators(date=None):
    """
    Get market indicators for a specific date.
    
    Args:
        date (str): Date in YYYY-MM-DD format
        
    Returns:
        dict: Market indicators including VIX, SPX level, etc.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Use 30 days of historical data to calculate indicators
    start_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Use AAPL instead of SPX since we don't have API access for SPX
    spx_prices = get_cached_prices(ticker="AAPL", start_date=start_date, end_date=date)
    
    if not spx_prices or "prices" not in spx_prices:
        # If we can't get real data, generate synthetic data
        return {
            "vix": 18.5,
            "spx_level": 4800.0,
            "interest_rate": 0.0525,
            "historical_volatility": 0.15,
            "market_regime": "normal",
            "date": date
        }
    
    # Calculate indicators from price data
    prices_df = prices_to_df(spx_prices)
    
    # Calculate historical volatility (annualized)
    if len(prices_df) > 1:
        log_returns = np.log(prices_df['close'] / prices_df['close'].shift(1)).dropna()
        historical_volatility = np.std(log_returns) * np.sqrt(252)  # Annualize
    else:
        historical_volatility = 0.15  # Default if not enough data
    
    # Use the most recent price as the SPX level
    spx_level = prices_df['close'].iloc[-1] if not prices_df.empty else 4800.0
    
    # Synthetic VIX calculation (in a real system, you would fetch actual VIX data)
    vix = historical_volatility * 100 * (1.0 + 0.1 * np.random.randn())
    
    # Determine market regime based on VIX
    if vix < 15:
        market_regime = "low_volatility"
    elif vix > 25:
        market_regime = "high_volatility"
    else:
        market_regime = "normal"
    
    return {
        "vix": vix,
        "spx_level": spx_level,
        "interest_rate": 0.0525,  # Current approximate Fed Funds rate
        "historical_volatility": historical_volatility,
        "market_regime": market_regime,
        "date": date
    }
