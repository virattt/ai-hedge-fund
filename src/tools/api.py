from datetime import datetime
import os
from typing import Dict, Any, List, Optional
from matplotlib.dates import relativedelta
import pandas as pd
import requests

class Cache:
    """In-memory cache for API responses."""
    def __init__(self):
        self._prices_cache: Dict[str, Dict[str, Any]] = {}
        self._financial_metrics_cache: Dict[str, Dict[str, Any]] = {}
        self._line_items_cache: Dict[str, Dict[str, Any]] = {}
        self._insider_trades_cache: Dict[str, Dict[str, Any]] = {}
    
    def _make_key(self, **kwargs) -> str:
        """Create a cache key from the parameters."""
        return "_".join(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    
    def get_prices(self, ticker: str, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached price data if available."""
        key = self._make_key(ticker=ticker, start_date=start_date, end_date=end_date)
        return self._prices_cache.get(key)
    
    def set_prices(self, ticker: str, start_date: str, end_date: str, data: List[Dict[str, Any]]):
        """Cache price data."""
        key = self._make_key(ticker=ticker, start_date=start_date, end_date=end_date)
        self._prices_cache[key] = data
    
    def get_financial_metrics(self, ticker: str, end_date: str, period: str = 'ttm', limit: int = 1) -> Optional[List[Dict[str, Any]]]:
        """Get cached financial metrics if available."""
        key = self._make_key(ticker=ticker, end_date=end_date, period=period, limit=limit)
        return self._financial_metrics_cache.get(key)
    
    def set_financial_metrics(self, ticker: str, end_date: str, period: str, limit: int, data: List[Dict[str, Any]]):
        """Cache financial metrics data."""
        key = self._make_key(ticker=ticker, end_date=end_date, period=period, limit=limit)
        self._financial_metrics_cache[key] = data
    
    def get_line_items(self, ticker: str, line_items: List[str], end_date: str, period: str = 'ttm', limit: int = 1) -> Optional[List[Dict[str, Any]]]:
        """Get cached line items if available."""
        key = self._make_key(ticker=ticker, end_date=end_date, period=period, limit=limit, line_items=",".join(sorted(line_items)))
        return self._line_items_cache.get(key)
    
    def set_line_items(self, ticker: str, line_items: List[str], end_date: str, period: str, limit: int, data: List[Dict[str, Any]]):
        """Cache line items data."""
        key = self._make_key(ticker=ticker, end_date=end_date, period=period, limit=limit, line_items=",".join(sorted(line_items)))
        self._line_items_cache[key] = data
    
    def get_insider_trades(self, ticker: str, end_date: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """Get cached insider trades if available."""
        key = self._make_key(ticker=ticker, end_date=end_date, limit=limit)
        return self._insider_trades_cache.get(key)
    
    def set_insider_trades(self, ticker: str, end_date: str, limit: int, data: List[Dict[str, Any]]):
        """Cache insider trades data."""
        key = self._make_key(ticker=ticker, end_date=end_date, limit=limit)
        self._insider_trades_cache[key] = data

# Global cache instance
_cache = Cache()

def get_prices(
    ticker: str,
    start_date: str,
    end_date: str
) -> List[Dict[str, Any]]:
    """Fetch price data from cache or API."""
    # Check cache first
    if cached_data := _cache.get_prices(ticker, start_date, end_date):
        return cached_data
        
    # If not in cache, fetch from API
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key
        
    url = (
        f"https://api.financialdatasets.ai/prices/"
        f"?ticker={ticker}"
        f"&interval=day"
        f"&interval_multiplier=1"
        f"&start_date={start_date}"
        f"&end_date={end_date}"
    )
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"Error fetching data: {response.status_code} - {response.text}"
        )
    data = response.json()
    prices = data.get("prices")
    if not prices:
        raise ValueError("No price data returned")
    
    # Cache the results
    _cache.set_prices(ticker, start_date, end_date, prices)
    return prices

def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = 'ttm',
    limit: int = 1
) -> List[Dict[str, Any]]:
    """Fetch financial metrics from cache or API."""
    # Check cache first
    if cached_data := _cache.get_financial_metrics(ticker):
        return cached_data
    
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key
    
    url = (
        f"https://api.financialdatasets.ai/financial-metrics/"
        f"?ticker={ticker}"
        f"&report_period_lte={end_date}"
        f"&limit={limit}"
        f"&period={period}"
    )
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"Error fetching data: {response.status_code} - {response.text}"
        )
    data = response.json()
    financial_metrics = data.get("financial_metrics")
    if not financial_metrics:
        raise ValueError("No financial metrics returned")
    
    # Cache the results
    _cache.set_financial_metrics(ticker, end_date, period, limit, financial_metrics)
    return financial_metrics

def search_line_items(
    ticker: str,
    line_items: List[str],
    end_date: str,
    period: str = 'ttm',
    limit: int = 1
) -> List[Dict[str, Any]]:
    """Fetch line items from cache or API."""
    # Check cache first
    if cached_data := _cache.get_line_items(ticker, line_items, end_date, period, limit):
        return cached_data
    
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key

    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit
    }
    response = requests.post(url, headers=headers, json=body)
    if response.status_code != 200:
        raise Exception(
            f"Error fetching data: {response.status_code} - {response.text}"
        )
    data = response.json()
    search_results = data.get("search_results")
    if not search_results:
        raise ValueError("No search results returned")
    
    # Cache the results
    _cache.set_line_items(ticker, line_items, end_date, period, limit, search_results)
    return search_results

def get_insider_trades(
    ticker: str,
    end_date: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Fetch insider trades from cache or API."""
    # Check cache first
    if cached_data := _cache.get_insider_trades(ticker, end_date, limit):
        return cached_data
    
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key
    
    url = (
        f"https://api.financialdatasets.ai/insider-trades/"
        f"?ticker={ticker}"
        f"&filing_date_lte={end_date}"
        f"&limit={limit}"
    )
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"Error fetching data: {response.status_code} - {response.text}"
        )
    data = response.json()
    insider_trades = data.get("insider_trades")
    if not insider_trades:
        raise ValueError("No insider trades returned")
    
    # Cache the results
    _cache.set_insider_trades(ticker, end_date, limit, insider_trades)
    return insider_trades

def get_market_cap(
    ticker: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Fetch market cap from the API."""
    financial_metrics = get_financial_metrics(ticker, end_date)
    market_cap = financial_metrics[0].get('market_cap')
    if not market_cap:
        raise ValueError("No market cap returned")
    
    return market_cap

def prices_to_df(prices: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame(prices)
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df

# Update the get_price_data function to use the new functions
def get_price_data(
    ticker: str,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date)
    return prices_to_df(prices)
