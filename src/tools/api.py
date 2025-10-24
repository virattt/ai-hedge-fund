"""
Unified API Module - Router

This module routes API calls to either Financial Datasets API or Yahoo Finance
based on the USE_YAHOO_FINANCE environment variable.

Usage:
    - Set USE_YAHOO_FINANCE=true to use Yahoo Finance (free)
    - Leave unset or set to false to use Financial Datasets API (paid)

All existing code will continue to work without changes.
"""

from src.tools.api_config import get_api_provider
import pandas as pd
from typing import Optional

from src.data.models import (
    Price,
    FinancialMetrics,
    LineItem,
    InsiderTrade,
    CompanyNews,
)

# Determine which API to use
_api_provider = get_api_provider()

# Import the appropriate implementation
if _api_provider == "yahoo_finance":
    from src.tools import api_yahoo as _api_impl
    print("📊 Using Yahoo Finance API (Free)")
else:
    from src.tools import api_financial_datasets as _api_impl
    print("📊 Using Financial Datasets API (Paid)")


# Export all functions from the selected implementation
def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """
    Fetch historical price data (OHLCV).

    Args:
        ticker: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        api_key: API key (only used for Financial Datasets)

    Returns:
        List of Price objects
    """
    return _api_impl.get_prices(ticker, start_date, end_date, api_key)


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """
    Fetch financial metrics (valuation ratios, profitability, etc.).

    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        period: Period type (ttm, quarterly, annual)
        limit: Number of periods to return
        api_key: API key (only used for Financial Datasets)

    Returns:
        List of FinancialMetrics objects
    """
    return _api_impl.get_financial_metrics(ticker, end_date, period, limit, api_key)


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """
    Search for specific line items in financial statements.

    Args:
        ticker: Stock ticker symbol
        line_items: List of line item names (e.g., "revenue", "free_cash_flow")
        end_date: End date (YYYY-MM-DD)
        period: Period type (ttm, quarterly, annual)
        limit: Number of periods to return
        api_key: API key (only used for Financial Datasets)

    Returns:
        List of LineItem objects
    """
    return _api_impl.search_line_items(ticker, line_items, end_date, period, limit, api_key)


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """
    Fetch insider trading data.

    Note: Returns empty list when using Yahoo Finance (not available).

    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        start_date: Start date (YYYY-MM-DD, optional)
        limit: Max number of trades
        api_key: API key (only used for Financial Datasets)

    Returns:
        List of InsiderTrade objects (empty for Yahoo Finance)
    """
    return _api_impl.get_insider_trades(ticker, end_date, start_date, limit, api_key)


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """
    Fetch company news articles.

    Note: Sentiment field will be None when using Yahoo Finance.

    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        start_date: Start date (YYYY-MM-DD, optional)
        limit: Max number of articles
        api_key: API key (only used for Financial Datasets)

    Returns:
        List of CompanyNews objects
    """
    return _api_impl.get_company_news(ticker, end_date, start_date, limit, api_key)


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """
    Fetch market capitalization.

    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        api_key: API key (only used for Financial Datasets)

    Returns:
        Market cap as float, or None if not available
    """
    return _api_impl.get_market_cap(ticker, end_date, api_key)


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """
    Convert prices to a pandas DataFrame.

    Args:
        prices: List of Price objects

    Returns:
        DataFrame with OHLCV data indexed by date
    """
    return _api_impl.prices_to_df(prices)


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    """
    Get price data as a pandas DataFrame (convenience function).

    Args:
        ticker: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        api_key: API key (only used for Financial Datasets)

    Returns:
        DataFrame with OHLCV data
    """
    return _api_impl.get_price_data(ticker, start_date, end_date, api_key)


# Print API configuration on import
def _print_api_status():
    """Print which API is being used."""
    from src.tools.api_config import get_api_info

    info = get_api_info()
    print(f"\n{'='*60}")
    print(f"Financial Data Provider: {info['provider']}")
    print(f"Cost: {info['cost']}")

    if not info['capabilities']['insider_trades']:
        print("⚠️  Note: Insider trading data not available")
    if not info['capabilities']['news_sentiment']:
        print("⚠️  Note: News sentiment analysis not available")

    print(f"{'='*60}\n")


# Only print status once on first import
if _api_provider == "yahoo_finance":
    _print_api_status()
