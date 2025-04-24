import datetime
from datetime import timedelta
import os
import pandas as pd
import requests
from typing import Optional, List, TypeVar, Generic, Callable, Dict, Any

from data.cache import get_cache
from data.models import (
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

# Global cache instance
_cache = get_cache()

# TypeVar for generic pagination function
T = TypeVar('T')


class APIError(Exception):
    """Custom exception for API errors"""
    def __init__(self, ticker: str, status_code: int, message: str):
        self.ticker = ticker
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error for {ticker}: {status_code} - {message}")


def _get_headers() -> Dict[str, str]:
    """Get API headers with key if available"""
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key
    return headers


def _paginate_api_calls(
    ticker: str,
    url_template: str, 
    response_parser: Callable[[Dict[str, Any]], List[T]],
    start_date: Optional[str],
    end_date: str,
    date_field: str,
    limit: int = 1000,
) -> List[T]:
    """Generic pagination function for API calls"""
    headers = _get_headers()
    all_items = []
    current_end_date = end_date
    
    while True:
        url = url_template.format(
            ticker=ticker, 
            end_date=current_end_date,
            start_date=f"&start_date={start_date}" if start_date else "",
            limit=limit
        )
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise APIError(ticker, response.status_code, response.text)
        
        data = response.json()
        items = response_parser(data)
        
        if not items:
            break
            
        all_items.extend(items)
        
        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(items) < limit:
            break
            
        # Update end_date to the oldest date from current batch for next iteration
        current_end_date = min(getattr(item, date_field) for item in items).split('T')[0]
        
        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break
    
    return all_items


def get_prices(ticker: str, start_date: str, end_date: str) -> List[Price]:
    """
    Fetch price data from cache or API.
    
    Price data is particularly time-sensitive, so we use a shorter TTL.
    """
    # Check cache first
    if cached_data := _cache.get_prices(ticker):
        # Filter cached data by date range and convert to Price objects
        filtered_data = [Price(**price) for price in cached_data if start_date <= price["time"] <= end_date]
        if filtered_data:
            return filtered_data

    # If not in cache or no data in range, fetch from API
    headers = _get_headers()

    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise APIError(ticker, getattr(e.response, 'status_code', 0), str(e))

    # Parse response with Pydantic model
    price_response = PriceResponse(**response.json())
    prices = price_response.prices

    if not prices:
        return []

    # Cache the results as dicts with a shorter TTL for price data (e.g., 1 hour)
    _cache.set_prices(ticker, [p.model_dump() for p in prices], ttl=timedelta(hours=1))
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> List[FinancialMetrics]:
    """
    Fetch financial metrics from cache or API.
    
    Financial metrics update quarterly, so we use a longer TTL.
    """
    # Check cache first
    if cached_data := _cache.get_financial_metrics(ticker):
        # Filter cached data by date and limit
        filtered_data = [FinancialMetrics(**metric) for metric in cached_data if metric["report_period"] <= end_date]
        filtered_data.sort(key=lambda x: x.report_period, reverse=True)
        if filtered_data:
            return filtered_data[:limit]

    # If not in cache or insufficient data, fetch from API
    headers = _get_headers()

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise APIError(ticker, getattr(e.response, 'status_code', 0), str(e))

    # Parse response with Pydantic model
    metrics_response = FinancialMetricsResponse(**response.json())
    financial_metrics = metrics_response.financial_metrics

    if not financial_metrics:
        return []

    # Cache the results as dicts with a longer TTL for financial data (e.g., 1 week)
    _cache.set_financial_metrics(ticker, [m.model_dump() for m in financial_metrics], ttl=timedelta(days=7))
    return financial_metrics


def search_line_items(
    ticker: str,
    line_items: List[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> List[LineItem]:
    """
    Fetch line items from API.
    
    Since this is a search endpoint rather than a direct fetch, we don't cache these results.
    """
    headers = _get_headers()
    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    
    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise APIError(ticker, getattr(e.response, 'status_code', 0), str(e))
    
    data = response.json()
    response_model = LineItemResponse(**data)
    search_results = response_model.search_results
    
    return search_results[:limit] if search_results else []


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: Optional[str] = None,
    limit: int = 1000,
) -> List[InsiderTrade]:
    """
    Fetch insider trades from cache or API.
    
    Uses the generic pagination function.
    """
    # Check cache first
    if cached_data := _cache.get_insider_trades(ticker):
        # Filter cached data by date range
        filtered_data = [InsiderTrade(**trade) for trade in cached_data 
                        if (start_date is None or (trade.get("transaction_date") or trade["filing_date"]) >= start_date)
                        and (trade.get("transaction_date") or trade["filing_date"]) <= end_date]
        filtered_data.sort(key=lambda x: x.transaction_date or x.filing_date, reverse=True)
        if filtered_data:
            return filtered_data

    # If not in cache, use pagination function
    def parse_insider_trades(data: Dict[str, Any]) -> List[InsiderTrade]:
        response_model = InsiderTradeResponse(**data)
        return response_model.insider_trades
    
    url_template = "https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={end_date}{start_date}&limit={limit}"
    
    try:
        all_trades = _paginate_api_calls(
            ticker=ticker,
            url_template=url_template,
            response_parser=parse_insider_trades,
            start_date=start_date,
            end_date=end_date,
            date_field="filing_date",
            limit=limit
        )
    except Exception as e:
        if isinstance(e, APIError):
            raise
        raise APIError(ticker, 0, str(e))

    if not all_trades:
        return []

    # Cache the results with a medium TTL (e.g., 2 days)
    _cache.set_insider_trades(ticker, [trade.model_dump() for trade in all_trades], ttl=timedelta(days=2))
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: Optional[str] = None,
    limit: int = 1000,
) -> List[CompanyNews]:
    """
    Fetch company news from cache or API.
    
    Uses the generic pagination function.
    """
    # Check cache first
    if cached_data := _cache.get_company_news(ticker):
        # Filter cached data by date range
        filtered_data = [CompanyNews(**news) for news in cached_data 
                        if (start_date is None or news["date"] >= start_date)
                        and news["date"] <= end_date]
        filtered_data.sort(key=lambda x: x.date, reverse=True)
        if filtered_data:
            return filtered_data

    # If not in cache, use pagination function
    def parse_company_news(data: Dict[str, Any]) -> List[CompanyNews]:
        response_model = CompanyNewsResponse(**data)
        return response_model.news
    
    url_template = "https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={end_date}{start_date}&limit={limit}"
    
    try:
        all_news = _paginate_api_calls(
            ticker=ticker,
            url_template=url_template,
            response_parser=parse_company_news,
            start_date=start_date,
            end_date=end_date,
            date_field="date",
            limit=limit
        )
    except Exception as e:
        if isinstance(e, APIError):
            raise
        raise APIError(ticker, 0, str(e))

    if not all_news:
        return []

    # Cache the results with a shorter TTL for news (e.g., 4 hours)
    _cache.set_company_news(ticker, [news.model_dump() for news in all_news], ttl=timedelta(hours=4))
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
) -> Optional[float]:
    """Fetch market cap from the API."""
    # Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Get the market cap from company facts API
        headers = _get_headers()
            
        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching company facts: {ticker} - {getattr(e.response, 'status_code', 0)}")
            return None
            
        data = response.json()
        response_model = CompanyFactsResponse(**data)
        return response_model.company_facts.market_cap

    # If not today, get from financial metrics
    try:
        financial_metrics = get_financial_metrics(ticker, end_date)
        if not financial_metrics:
            return None
        
        market_cap = financial_metrics[0].market_cap
        return market_cap
    except Exception as e:
        print(f"Error getting market cap from financial metrics: {ticker} - {str(e)}")
        return None


def prices_to_df(prices: List[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    if not prices:
        return pd.DataFrame()
        
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Get price data as a DataFrame."""
    try:
        prices = get_prices(ticker, start_date, end_date)
        return prices_to_df(prices)
    except Exception as e:
        print(f"Error getting price data: {ticker} - {str(e)}")
        return pd.DataFrame()