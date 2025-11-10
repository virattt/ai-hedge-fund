import datetime
import os
import pandas as pd
import requests
import time

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

# Global cache instance
_cache = get_cache()


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate limiting handling and moderate backoff.
    
    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)
    
    Returns:
        requests.Response: The response object
    
    Raises:
        Exception: If the request fails with a non-429 error
    """
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 429 and attempt < max_retries:
            # Linear backoff: 60s, 90s, 120s, 150s...
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue
        
        # Return the response (whether success, other errors, or final 429)
        return response


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Fetch price data from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

    # Parse response with Pydantic model
    price_response = PriceResponse(**response.json())
    prices = price_response.prices

    if not prices:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or API."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Check cache first
    cached_data = _cache.get_financial_metrics(ticker, period)
    
    # Check if we need to refresh cache
    # Refresh if cache doesn't exist or latest report_period is before today
    latest_cached_date = _cache.get_latest_financial_metrics_date(ticker, period)
    need_refresh = latest_cached_date is None or latest_cached_date < today
    
    # If cache needs refresh, fetch data up to today from API
    if need_refresh:
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        # Always fetch data up to today (using today as end_date)
        url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={today}&limit=100&period={period}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        # Parse response with Pydantic model
        metrics_response = FinancialMetricsResponse(**response.json())
        financial_metrics = metrics_response.financial_metrics

        if financial_metrics:
            # Cache the results (only ticker and period in cache key)
            _cache.set_financial_metrics(ticker, period, [m.model_dump() for m in financial_metrics])
            # Update cached_data for filtering
            cached_data = _cache.get_financial_metrics(ticker, period)
    
    # Filter cached data based on end_date and limit
    if not cached_data:
        return []
    
    # Filter by end_date (report_period <= end_date) and limit
    filtered_data = [
        metric for metric in cached_data 
        if metric.get("report_period", "") <= end_date
    ][:limit]
    
    return [FinancialMetrics(**metric) for metric in filtered_data]


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch line items from cache or API."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Check cache first (only by ticker and period, no end_date/limit/line_items)
    cached_data = _cache.get_line_items(ticker, period)
    
    # Common line items list for initial fetch (comprehensive list)
    
    common_line_items = [
        "ebit",
        "interest_expense",
        "capital_expenditure",
        "depreciation_and_amortization",
        "outstanding_shares",
        "net_income",
        "total_debt",
        "earnings_per_share", 
        "revenue", 
        "book_value_per_share", 
        "total_assets", 
        "total_liabilities", 
        "current_assets", 
        "current_liabilities",
        "dividends_and_other_cash_distributions",
        "operating_margin",
        "debt_to_equity",
        "free_cash_flow",
        "gross_margin",
        "research_and_development",
        "operating_expense",
        "operating_income",
        "return_on_invested_capital",
        "cash_and_equivalents",
        "shareholders_equity",
        "goodwill_and_intangible_assets",
        "issuance_or_purchase_of_equity_shares",
        "gross_profit",
        "ebitda",
        "working_capital",   
    ]
    
    # If cache doesn't exist, fetch all available line items
    if not cached_data:
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = "https://api.financialdatasets.ai/financials/search/line-items"

        # First fetch: get all common line items with large limit and today's date
        body = {
            "tickers": [ticker],
            "line_items": common_line_items,
            "end_date": today,
            "period": period,
            "limit": 1000,  # Large limit to get all available periods
        }
        response = _make_api_request(url, headers, method="POST", json_data=body)
        if response.status_code != 200:
            # If failed, try with empty line_items to get all available
            body["line_items"] = []
            response = _make_api_request(url, headers, method="POST", json_data=body)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
        
        data = response.json()
        response_model = LineItemResponse(**data)
        search_results = response_model.search_results

        if search_results:
            # Cache all results (only ticker and period in cache key)
            _cache.set_line_items(ticker, period, [item.model_dump() for item in search_results])
            # Update cached_data for filtering
            cached_data = _cache.get_line_items(ticker, period)
    
    # Filter cached data based on line_items, end_date, and limit
    if not cached_data:
        return []
    
    filtered_items = []
    for item in cached_data:
        item_report_period = item.get("report_period", "")
        
        # Filter by end_date (report_period <= end_date)
        if item_report_period > end_date:
            continue
        
        # Filter by requested line_items (check if any requested line_item exists in the item)
        item_dict = dict(item)
        has_requested_line_item = False
        for requested_item in line_items:
            # Check if the requested line_item exists as a key in the item
            if requested_item in item_dict and item_dict[requested_item] is not None:
                has_requested_line_item = True
                break
        
        if not has_requested_line_item:
            continue
        
        filtered_items.append(item)
    
    # Sort by report_period descending (newest first)
    filtered_items.sort(key=lambda x: x.get("report_period", ""), reverse=True)
    
    # Apply limit
    filtered_items = filtered_items[:limit]
    
    return [LineItem(**item) for item in filtered_items]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Check cache first (only by ticker, no start_date/end_date/limit)
    cached_data = _cache.get_insider_trades(ticker)
    
    # Calculate one year ago date for default fetch
    one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    # If cache doesn't exist, fetch default one year of data
    if not cached_data:
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        all_trades = []
        current_end_date = today

        # Fetch one year of data by default
        while True:
            url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}&filing_date_gte={one_year_ago}&limit=1000"

            response = _make_api_request(url, headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

            data = response.json()
            response_model = InsiderTradeResponse(**data)
            insider_trades = response_model.insider_trades

            if not insider_trades:
                break

            all_trades.extend(insider_trades)

            # Check if we got a full page
            if len(insider_trades) < 1000:
                break

            # Update end_date to the oldest filing date from current batch for next iteration
            current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

            # If we've reached or passed the start_date, we can stop
            if current_end_date <= one_year_ago:
                break

        if all_trades:
            # Cache the results (only ticker in cache key)
            _cache.set_insider_trades(ticker, [trade.model_dump() for trade in all_trades])
            # Update cached_data for filtering
            cached_data = _cache.get_insider_trades(ticker)
    
    # Filter cached data based on start_date, end_date, and limit
    if not cached_data:
        return []
    
    filtered_trades = []
    for trade in cached_data:
        filing_date = trade.get("filing_date", "")
        # Extract date part if it includes time
        trade_date = filing_date.split("T")[0] if "T" in filing_date else filing_date
        
        # Filter by date range
        if trade_date > end_date:
            continue
        if start_date and trade_date < start_date:
            continue
        
        filtered_trades.append(trade)
    
    # Sort by filing_date descending (newest first) to match cache order
    filtered_trades.sort(key=lambda x: x.get("filing_date", ""), reverse=True)
    
    # Apply limit
    filtered_trades = filtered_trades[:limit]
    
    return [InsiderTrade(**trade) for trade in filtered_trades]


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news from cache or API."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Check cache first (only by ticker, no start_date/end_date/limit)
    cached_data = _cache.get_company_news(ticker)
    
    # Calculate one year ago date for default fetch
    one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    # If cache doesn't exist, fetch default one year of data
    if not cached_data:
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        all_news = []
        current_end_date = today

        # Fetch one year of data by default
        while True:
            url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}&start_date={one_year_ago}&limit=1000"

            response = _make_api_request(url, headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

            data = response.json()
            response_model = CompanyNewsResponse(**data)
            company_news = response_model.news

            if not company_news:
                break

            all_news.extend(company_news)

            # Check if we got a full page
            if len(company_news) < 1000:
                break

            # Update end_date to the oldest date from current batch for next iteration
            current_end_date = min(news.date for news in company_news).split("T")[0]

            # If we've reached or passed the start_date, we can stop
            if current_end_date <= one_year_ago:
                break

        if all_news:
            # Cache the results (only ticker in cache key)
            _cache.set_company_news(ticker, [news.model_dump() for news in all_news])
            # Update cached_data for filtering
            cached_data = _cache.get_company_news(ticker)
    
    # Filter cached data based on start_date, end_date, and limit
    if not cached_data:
        return []
    
    filtered_news = []
    for news in cached_data:
        news_date = news.get("date", "")
        # Extract date part if it includes time
        article_date = news_date.split("T")[0] if "T" in news_date else news_date
        
        # Filter by date range
        if article_date > end_date:
            continue
        if start_date and article_date < start_date:
            continue
        
        filtered_news.append(news)
    
    # Sort by date descending (newest first) to match cache order
    filtered_news.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    # Apply limit
    filtered_news = filtered_news[:limit]
    
    return [CompanyNews(**news) for news in filtered_news]


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap from cache or API."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Check cache first - try to get market cap for the specific end_date
    cached_market_cap = _cache.get_market_cap_by_date(ticker, end_date)
    if cached_market_cap is not None:
        return cached_market_cap
    
    # Cache doesn't have data for end_date, check if we need to refresh
    latest_cached_date = _cache.get_latest_market_cap_date(ticker)
    need_refresh = latest_cached_date is None or latest_cached_date != today
    
    # If end_date is today, check if we need to refresh cache
    if end_date == today:
        # If cache doesn't exist or latest date is not today, refresh
        if need_refresh:
            headers = {}
            financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
            if financial_api_key:
                headers["X-API-KEY"] = financial_api_key

            url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
            response = _make_api_request(url, headers)
            if response.status_code != 200:
                print(f"Error fetching company facts: {ticker} - {response.status_code}")
                return None

            data = response.json()
            response_model = CompanyFactsResponse(**data)
            market_cap = response_model.company_facts.market_cap
            
            # Cache the result
            if market_cap is not None:
                _cache.set_market_cap(ticker, [{"date": today, "market_cap": market_cap}])
            
            return market_cap
        else:
            # Cache exists and latest date is today, but no data for today
            # This shouldn't happen, but return None if it does
            return None
    
    # For historical dates, fetch from financial_metrics API
    financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap

    if not market_cap:
        return None

    # Cache the result
    _cache.set_market_cap(ticker, [{"date": end_date, "market_cap": market_cap}])
    
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
def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
