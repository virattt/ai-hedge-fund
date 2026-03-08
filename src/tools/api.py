import datetime
import os

import pandas as pd

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
    """Fetch price data from cache or multi-source API (FD -> yfinance -> Alpha Vantage)."""
    return _get_router().get_prices(ticker, start_date, end_date, api_key=api_key)


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or multi-source API."""
    return _get_router().get_financial_metrics(
        ticker, end_date, period=period, limit=limit, api_key=api_key
    )


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch line items (Financial Datasets only; others have no line-item API)."""
    return _get_router().search_line_items(
        ticker, line_items, end_date, period=period, limit=limit, api_key=api_key
    )


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API (Financial Datasets only)."""
    return _get_router().get_insider_trades(
        ticker, end_date, start_date=start_date, limit=limit, api_key=api_key
    )


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news from cache or multi-source API."""
    return _get_router().get_company_news(
        ticker, end_date, start_date=start_date, limit=limit, api_key=api_key
    )


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
