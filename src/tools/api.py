import datetime
import os
import pandas as pd
import requests
import time
import logging
import random
from typing import List, Optional
from threading import Lock

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

# Set up logging
logger = logging.getLogger(__name__)


def _get_configured_rate_limit() -> int:
    """
    Get the configured API rate limit per minute from environment variable.
    
    Returns:
        int: Rate limit per minute (default: 90)
        
    Raises:
        ValueError: If the environment variable contains an invalid value
    """
    default_rate_limit = 90
    env_value = os.environ.get("API_RATE_LIMIT_PER_MINUTE")
    
    if env_value is None:
        logger.info(f"API_RATE_LIMIT_PER_MINUTE not set, using default: {default_rate_limit} calls/minute")
        return default_rate_limit
    
    try:
        rate_limit = int(env_value)
        
        # Validation: Ensure reasonable bounds
        if rate_limit <= 0:
            logger.warning(f"Invalid API_RATE_LIMIT_PER_MINUTE value '{env_value}' (must be > 0), using default: {default_rate_limit}")
            return default_rate_limit
        elif rate_limit > 10000:  # Sanity check for extremely high values
            logger.warning(f"API_RATE_LIMIT_PER_MINUTE value '{env_value}' seems unusually high (>10000), using anyway")
            return rate_limit
        else:
            logger.info(f"Using configured API rate limit: {rate_limit} calls/minute")
            return rate_limit
            
    except ValueError as e:
        logger.error(f"Invalid API_RATE_LIMIT_PER_MINUTE value '{env_value}' (must be an integer), using default: {default_rate_limit}")
        return default_rate_limit


# Global cache instance
_cache = get_cache()

# Rate limiting configuration - configurable via environment variable with validation
_rate_limit_lock = Lock()
_last_request_times = []
# FIX: Make API rate limit configurable via environment variable with proper validation
# Default is 90 calls per minute (conservative estimate for Credits plan)
# Set via environment variable: API_RATE_LIMIT_PER_MINUTE=120 (example)
_max_requests_per_minute = _get_configured_rate_limit()


def _enforce_rate_limit():
    """
    Enforce configurable rate limiting to prevent hitting API limits.
    Rate limit is configurable via API_RATE_LIMIT_PER_MINUTE environment variable.
    Default: 90 requests per minute (conservative estimate for Credits plan)
    """
    with _rate_limit_lock:
        current_time = time.time()
        # Remove requests older than 1 minute
        _last_request_times[:] = [t for t in _last_request_times if current_time - t < 60]
        
        # If we're at the limit, wait
        if len(_last_request_times) >= _max_requests_per_minute:
            oldest_request = min(_last_request_times)
            wait_time = 60 - (current_time - oldest_request) + 1  # Add 1 second buffer
            if wait_time > 0:
                logger.info(f"Rate limit reached ({_max_requests_per_minute} calls/minute), waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                # Clean up old requests again after waiting
                current_time = time.time()
                _last_request_times[:] = [t for t in _last_request_times if current_time - t < 60]
        
        # Record this request
        _last_request_times.append(current_time)
        
        # Debug logging for monitoring rate limit usage
        if len(_last_request_times) % 10 == 0:  # Log every 10th request
            logger.debug(f"API rate limit usage: {len(_last_request_times)}/{_max_requests_per_minute} calls in last minute")


def _make_api_request_with_retry(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3, backoff_factor: float = 3.0) -> requests.Response:
    """
    Make an API request with retry logic and exponential backoff.
    
    Args:
        url: The API endpoint URL
        headers: Request headers
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff multiplier for retry delays
        
    Returns:
        Response object
        
    Raises:
        Exception: If all retries fail
    """
    # Enforce rate limiting before making request
    _enforce_rate_limit()
    
    for attempt in range(max_retries + 1):
        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=headers, json=json_data, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)
            
            # If successful or client error (4xx), return immediately
            if response.status_code < 500:
                return response
            
            # For server errors (5xx), retry with backoff
            if attempt < max_retries:
                wait_time = backoff_factor * (2 ** attempt)
                logger.warning(f"API request failed with {response.status_code}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                # Add longer jitter for Credits plan rate limiting
                time.sleep(random.uniform(1, 3))
            else:
                # Last attempt failed
                logger.error(f"API request failed after {max_retries} retries: {response.status_code} - {response.text}")
                return response
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait_time = backoff_factor * (2 ** attempt)
                logger.warning(f"API request exception: {str(e)}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                # Add longer jitter for Credits plan rate limiting
                time.sleep(random.uniform(1, 3))
            else:
                logger.error(f"API request failed after {max_retries} retries: {str(e)}")
                raise Exception(f"API request failed: {str(e)}")
    
    return response


def get_prices(ticker: str, start_date: str, end_date: str) -> List[Price]:
    """Fetch price data from cache or API with improved error handling."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # If not in cache, fetch from API with retry logic
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key
    else:
        logger.warning("FINANCIAL_DATASETS_API_KEY not found in environment variables")

    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    
    try:
        response = _make_api_request_with_retry(url, headers)
        
        if response.status_code == 200:
            # Parse response with Pydantic model
            price_response = PriceResponse(**response.json())
            prices = price_response.prices

            if not prices:
                logger.warning(f"No price data found for {ticker}")
                return []

            # Cache the results using the comprehensive cache key
            _cache.set_prices(cache_key, [p.model_dump() for p in prices])
            return prices
        
        elif response.status_code == 404:
            logger.warning(f"Price data not found for ticker {ticker}")
            return []
        
        elif response.status_code == 429:
            logger.warning(f"Rate limit exceeded for ticker {ticker}")
            return []
        
        else:
            logger.error(f"API error for {ticker}: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Failed to fetch price data for {ticker}: {str(e)}")
        return []


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> List[FinancialMetrics]:
    """Fetch financial metrics from cache or API with improved error handling."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # If not in cache, fetch from API with retry logic
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key
    else:
        logger.warning("FINANCIAL_DATASETS_API_KEY not found in environment variables")

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    
    try:
        response = _make_api_request_with_retry(url, headers)
        
        if response.status_code == 200:
            # Parse response with Pydantic model
            metrics_response = FinancialMetricsResponse(**response.json())
            financial_metrics = metrics_response.financial_metrics

            if not financial_metrics:
                logger.warning(f"No financial metrics found for {ticker}")
                return []

            # Cache the results as dicts using the comprehensive cache key
            _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
            return financial_metrics
        
        elif response.status_code == 404:
            logger.warning(f"Financial metrics not found for ticker {ticker}")
            return []
        
        elif response.status_code == 429:
            logger.warning(f"Rate limit exceeded for ticker {ticker}")
            return []
        
        else:
            logger.error(f"API error for {ticker}: {response.status_code} - {response.text}")
            # Return empty list instead of raising exception to allow other agents to continue
            return []
            
    except Exception as e:
        logger.error(f"Failed to fetch financial metrics for {ticker}: {str(e)}")
        # Return empty list instead of raising exception to allow other agents to continue
        return []


def search_line_items(
    ticker: str,
    line_items: List[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> List[LineItem]:
    """Fetch line items from API with improved error handling."""
    # If not in cache or insufficient data, fetch from API with retry logic
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key
    else:
        logger.warning("FINANCIAL_DATASETS_API_KEY not found in environment variables")

    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    
    try:
        response = _make_api_request_with_retry(url, headers, method="POST", json_data=body)
        
        if response.status_code == 200:
            data = response.json()
            response_model = LineItemResponse(**data)
            search_results = response_model.search_results
            if not search_results:
                logger.warning(f"No line items found for {ticker}")
                return []

            # Cache the results
            return search_results[:limit]
        
        elif response.status_code == 404:
            logger.warning(f"Line items not found for ticker {ticker}")
            return []
        
        elif response.status_code == 429:
            logger.warning(f"Rate limit exceeded for ticker {ticker}")
            return []
        
        else:
            logger.error(f"API error for {ticker}: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Failed to fetch line items for {ticker}: {str(e)}")
        return []


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # If not in cache, fetch from API
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key

    all_trades = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        data = response.json()
        response_model = InsiderTradeResponse(**data)
        insider_trades = response_model.insider_trades

        if not insider_trades:
            break

        all_trades.extend(insider_trades)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(insider_trades) < limit:
            break

        # Update end_date to the oldest filing date from current batch for next iteration
        current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_trades:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[CompanyNews]:
    """Fetch company news from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    # If not in cache, fetch from API
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key

    all_news = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        data = response.json()
        response_model = CompanyNewsResponse(**data)
        company_news = response_model.news

        if not company_news:
            break

        all_news.extend(company_news)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(company_news) < limit:
            break

        # Update end_date to the oldest date from current batch for next iteration
        current_end_date = min(news.date for news in company_news).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_news:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
) -> float | None:
    """Fetch market cap from the API."""
    # Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Get the market cap from company facts API
        headers = {}
        if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
            headers["X-API-KEY"] = api_key

        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching company facts: {ticker} - {response.status_code}")
            return None

        data = response.json()
        response_model = CompanyFactsResponse(**data)
        return response_model.company_facts.market_cap

    financial_metrics = get_financial_metrics(ticker, end_date)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap

    if not market_cap:
        return None

    return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date)
    return prices_to_df(prices)
