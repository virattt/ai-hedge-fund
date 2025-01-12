import os
from typing import Dict, Any, List
import pandas as pd
import requests
from datetime import datetime
from pycoingecko import CoinGeckoAPI
import time

from data.cache import get_cache

# Global cache instance
_cache = get_cache()
_coingecko = CoinGeckoAPI()

# Add coin mapping cache
_coin_id_mapping = {}

def _get_coin_id(ticker: str) -> str:
    """Convert ticker symbol to CoinGecko coin id."""
    ticker = ticker.lower()
    
    # Check if mapping exists in cache
    if ticker in _coin_id_mapping:
        return _coin_id_mapping[ticker]
    
    # Fetch all coins list from CoinGecko
    try:
        coins_list = _coingecko.get_coins_list()
        # Create mapping of symbol to id
        for coin in coins_list:
            _coin_id_mapping[coin['symbol']] = coin['id']
        
        if ticker not in _coin_id_mapping:
            raise ValueError(f"Ticker {ticker} not found in CoinGecko")
            
        return _coin_id_mapping[ticker]
    except Exception as e:
        raise Exception(f"Error fetching coin ID: {str(e)}")

def get_prices(
    ticker: str,
    start_date: str,
    end_date: str
) -> List[Dict[str, Any]]:
    """Fetch price data from cache or CoinGecko API."""
    # Check cache first
    if cached_data := _cache.get_prices(ticker):
        # Filter cached data by date range
        filtered_data = [
            price for price in cached_data 
            if start_date <= price["time"] <= end_date
        ]
        if filtered_data:
            return filtered_data
    
    try:
        # Convert dates to timestamps
        start_timestamp = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        end_timestamp = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
        
        # Get coin id from ticker
        coin_id = _get_coin_id(ticker)
        
        # Fetch data from CoinGecko
        data = _coingecko.get_coin_market_chart_range_by_id(
            id=coin_id,
            vs_currency='usd',
            from_timestamp=start_timestamp,
            to_timestamp=end_timestamp
        )
        
        # Transform data to match expected format
        prices = []
        for timestamp_ms, price in data['prices']:
            # Convert timestamp from milliseconds to ISO format
            time_str = datetime.fromtimestamp(timestamp_ms/1000).strftime('%Y-%m-%d')
            
            # Find matching OHLCV data
            matching_prices = [p for p in data['prices'] if datetime.fromtimestamp(p[0]/1000).strftime('%Y-%m-%d') == time_str]
            if matching_prices:
                day_prices = [p[1] for p in matching_prices]
                price_data = {
                    "time": time_str,
                    "open": day_prices[0],
                    "high": max(day_prices),
                    "low": min(day_prices),
                    "close": day_prices[-1],
                    "volume": 0  # CoinGecko provides volume in separate array
                }
                prices.append(price_data)
        
        # Cache the results
        _cache.set_prices(ticker, prices)
        return prices
        
    except Exception as e:
        raise Exception(f"Error fetching data from CoinGecko: {str(e)}")

def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = 'ttm',
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Fetch financial metrics from cache or API."""
    # Check cache first
    if cached_data := _cache.get_financial_metrics(ticker):
        # Filter cached data by date and limit
        filtered_data = [
            metric for metric in cached_data 
            if metric["report_period"] <= end_date
        ]
        filtered_data.sort(key=lambda x: x["report_period"], reverse=True)
        if filtered_data:
            return filtered_data[:limit]
    
    # If not in cache or insufficient data, fetch from API
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
    _cache.set_financial_metrics(ticker, financial_metrics)
    return financial_metrics[:limit]

def search_line_items(
    ticker: str,
    line_items: List[str],
    end_date: str,
    period: str = 'ttm',
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Fetch line items from cache or API."""
    # Check cache first
    if cached_data := _cache.get_line_items(ticker):
        # Filter cached data by date and limit
        filtered_data = [
            item for item in cached_data 
            if item["report_period"] <= end_date
        ]
        filtered_data.sort(key=lambda x: x["report_period"], reverse=True)
        if filtered_data:
            return filtered_data[:limit]
    
    # If not in cache or insufficient data, fetch from API
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
    _cache.set_line_items(ticker, search_results)
    return search_results[:limit]

def get_insider_trades(
    ticker: str,
    end_date: str,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """Fetch insider trades from cache or API."""
    # Check cache first
    if cached_data := _cache.get_insider_trades(ticker):
        # Filter cached data by date and limit
        filtered_data = [
            trade for trade in cached_data 
            if (trade.get("transaction_date") or trade["filing_date"]) <= end_date
        ]
        # Sort by transaction_date if available, otherwise filing_date
        filtered_data.sort(
            key=lambda x: x.get("transaction_date") or x["filing_date"],
            reverse=True
        )
        if filtered_data:
            return filtered_data[:limit]
    
    # If not in cache or insufficient data, fetch from API
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
    _cache.set_insider_trades(ticker, insider_trades)
    return insider_trades[:limit]

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
