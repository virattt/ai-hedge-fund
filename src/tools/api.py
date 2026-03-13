import datetime
import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)
from src.data.router import DataRouter

# Global router: FinancialDatasets -> yfinance -> AlphaVantage, with file cache
_router = None


def _get_router() -> DataRouter:
    global _router
    if _router is None:
        _router = DataRouter(cache=get_cache(), api_key=os.environ.get("FINANCIAL_DATASETS_API_KEY"))
    return _router


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
<<<<<<< HEAD
    """Fetch price data from cache or multi-source API (FD -> yfinance -> Alpha Vantage)."""
    return _get_router().get_prices(ticker, start_date, end_date, api_key=api_key)
=======
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
        return []

    # Parse response with Pydantic model
    try:
        price_response = PriceResponse(**response.json())
        prices = price_response.prices
    except Exception as e:
        logger.warning("Failed to parse price response for %s: %s", ticker, e)
        return []

    if not prices:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices
>>>>>>> e32baad (fix: replace bare except clauses with Exception in api.py)


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
<<<<<<< HEAD
    """Fetch financial metrics from cache or multi-source API."""
    return _get_router().get_financial_metrics(
        ticker, end_date, period=period, limit=limit, api_key=api_key
    )
=======
    """Fetch financial metrics from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        return []

    # Parse response with Pydantic model
    try:
        metrics_response = FinancialMetricsResponse(**response.json())
        financial_metrics = metrics_response.financial_metrics
    except Exception as e:
        logger.warning("Failed to parse financial metrics response for %s: %s", ticker, e)
        return []

    if not financial_metrics:
        return []

    # Cache the results as dicts using the comprehensive cache key
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics
>>>>>>> e32baad (fix: replace bare except clauses with Exception in api.py)


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
<<<<<<< HEAD
    """Fetch line items (Financial Datasets only; others have no line-item API)."""
    return _get_router().search_line_items(
        ticker, line_items, end_date, period=period, limit=limit, api_key=api_key
    )
=======
    """Fetch line items from API."""
    # If not in cache or insufficient data, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    response = _make_api_request(url, headers, method="POST", json_data=body)
    if response.status_code != 200:
        return []
    
    try:
        data = response.json()
        response_model = LineItemResponse(**data)
        search_results = response_model.search_results
    except Exception as e:
        logger.warning("Failed to parse line items response for %s: %s", ticker, e)
        return []
    if not search_results:
        return []

    # Cache the results
    return search_results[:limit]
>>>>>>> e32baad (fix: replace bare except clauses with Exception in api.py)


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
<<<<<<< HEAD
    """Fetch insider trades from cache or API (Financial Datasets only)."""
    return _get_router().get_insider_trades(
        ticker, end_date, start_date=start_date, limit=limit, api_key=api_key
    )
=======
    """Fetch insider trades from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    all_trades = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        if response.status_code != 200:
            break

        try:
            data = response.json()
            response_model = InsiderTradeResponse(**data)
            insider_trades = response_model.insider_trades
        except Exception as e:
            logger.warning("Failed to parse insider trades response for %s: %s", ticker, e)
            break

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
>>>>>>> e32baad (fix: replace bare except clauses with Exception in api.py)


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
<<<<<<< HEAD
    """Fetch company news from cache or multi-source API."""
    return _get_router().get_company_news(
        ticker, end_date, start_date=start_date, limit=limit, api_key=api_key
    )
=======
    """Fetch company news from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    all_news = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        if response.status_code != 200:
            break

        try:
            data = response.json()
            response_model = CompanyNewsResponse(**data)
            company_news = response_model.news
        except Exception as e:
            logger.warning("Failed to parse company news response for %s: %s", ticker, e)
            break

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
>>>>>>> e32baad (fix: replace bare except clauses with Exception in api.py)


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap (tries all providers in order)."""
    return _get_router().get_market_cap(ticker, end_date, api_key=api_key)


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


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    """Fetch price data and return as DataFrame."""
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)


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
