import pandas as pd

from src.data.models import CompanyNews, FinancialMetrics, InsiderTrade, LineItem, Price
from src.data.providers.financial_datasets import _make_api_request
from src.data.providers.registry import get_financial_data_provider


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Fetch price data from the configured financial data provider."""
    return get_financial_data_provider().get_prices(ticker, start_date, end_date, api_key=api_key)


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from the configured financial data provider."""
    return get_financial_data_provider().get_financial_metrics(ticker, end_date, period=period, limit=limit, api_key=api_key)


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch financial statement line items from the configured financial data provider."""
    return get_financial_data_provider().search_line_items(ticker, line_items, end_date, period=period, limit=limit, api_key=api_key)


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from the configured financial data provider."""
    return get_financial_data_provider().get_insider_trades(ticker, end_date, start_date=start_date, limit=limit, api_key=api_key)


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news from the configured financial data provider."""
    return get_financial_data_provider().get_company_news(ticker, end_date, start_date=start_date, limit=limit, api_key=api_key)


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap from the configured financial data provider."""
    return get_financial_data_provider().get_market_cap(ticker, end_date, api_key=api_key)


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    if not prices:
        return pd.DataFrame(columns=["open", "close", "high", "low", "volume"])

    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
