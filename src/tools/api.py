"""Financial data API router.

Selects the data provider at call time based on the USE_FINANCE_DATA
environment variable (default: "Financial"). This allows per-request
provider switching (e.g. from the web app) without restarting the process.

Valid values
-----------
Financial   financialdatasets.ai — requires FINANCIAL_DATASETS_API_KEY
Yahoo       yfinance (free, no API key required)
Qveris      qveris.ai discovery platform — requires QVERIS_API_KEY

All three providers expose the same public interface:
    get_prices(ticker, start_date, end_date, api_key=None) -> list[Price]
    get_financial_metrics(ticker, end_date, period, limit, api_key=None) -> list[FinancialMetrics]
    search_line_items(ticker, line_items, end_date, period, limit, api_key=None) -> list[LineItem]
    get_insider_trades(ticker, end_date, start_date, limit, api_key=None) -> list[InsiderTrade]
    get_company_news(ticker, end_date, start_date, limit, api_key=None) -> list[CompanyNews]
    get_market_cap(ticker, end_date, api_key=None) -> float | None
    prices_to_df(prices) -> pd.DataFrame
    get_price_data(ticker, start_date, end_date, api_key=None) -> pd.DataFrame
"""

import os


def _get_backend():
    provider = os.environ.get("USE_FINANCE_DATA", "Financial").strip()
    if provider == "Yahoo":
        import src.tools.api_yahoo as _mod
    elif provider == "Qveris":
        import src.tools.api_qveris as _mod
    else:
        import src.tools.api_financial_datasets as _mod
    return _mod


def get_prices(ticker, start_date, end_date, api_key=None):
    return _get_backend().get_prices(ticker, start_date, end_date, api_key=api_key)


def get_financial_metrics(ticker, end_date, period="ttm", limit=10, api_key=None):
    return _get_backend().get_financial_metrics(ticker, end_date, period=period, limit=limit, api_key=api_key)


def search_line_items(ticker, line_items, end_date, period="ttm", limit=10, api_key=None):
    return _get_backend().search_line_items(ticker, line_items, end_date, period=period, limit=limit, api_key=api_key)


def get_insider_trades(ticker, end_date, start_date=None, limit=50, api_key=None):
    return _get_backend().get_insider_trades(ticker, end_date, start_date=start_date, limit=limit, api_key=api_key)


def get_company_news(ticker, end_date, start_date=None, limit=50, api_key=None):
    return _get_backend().get_company_news(ticker, end_date, start_date=start_date, limit=limit, api_key=api_key)


def get_market_cap(ticker, end_date, api_key=None):
    return _get_backend().get_market_cap(ticker, end_date, api_key=api_key)


def prices_to_df(prices):
    return _get_backend().prices_to_df(prices)


def get_price_data(ticker, start_date, end_date, api_key=None):
    return _get_backend().get_price_data(ticker, start_date, end_date, api_key=api_key)


__all__ = [
    "get_prices",
    "get_financial_metrics",
    "search_line_items",
    "get_insider_trades",
    "get_company_news",
    "get_market_cap",
    "prices_to_df",
    "get_price_data",
]
