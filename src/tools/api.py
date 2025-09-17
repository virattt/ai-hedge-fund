import os
import requests
import pandas as pd
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Alpha Vantage API key (set via env variable or "demo" for testing)
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
BASE_URL = "https://www.alphavantage.co/query"


# ---------------------------
# Core request helper
# ---------------------------
def _alpha_vantage_request(params: dict) -> dict:
    params["apikey"] = ALPHA_VANTAGE_API_KEY
    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200:
        logger.error(f"Alpha Vantage request failed: {response.text}")
        return {}
    try:
        return response.json()
    except Exception:
        logger.exception("Failed to parse Alpha Vantage response as JSON")
        return {}


# ---------------------------
# Price data
# ---------------------------
def get_prices(symbol: str, interval: str = "daily", outputsize: str = "compact", *args, **kwargs) -> Dict[str, Any]:
    """
    Fetch historical prices for a ticker symbol.
    Accepts extra kwargs (start_date, end_date, api_key) for compatibility.
    """
    function_map = {
        "daily": "TIME_SERIES_DAILY_ADJUSTED",
        "weekly": "TIME_SERIES_WEEKLY_ADJUSTED",
        "monthly": "TIME_SERIES_MONTHLY_ADJUSTED",
    }
    function = function_map.get(interval.lower(), "TIME_SERIES_DAILY_ADJUSTED")

    data = _alpha_vantage_request(
        {"function": function, "symbol": symbol, "outputsize": outputsize}
    )

    key_map = {
        "TIME_SERIES_DAILY_ADJUSTED": "Time Series (Daily)",
        "TIME_SERIES_WEEKLY_ADJUSTED": "Weekly Adjusted Time Series",
        "TIME_SERIES_MONTHLY_ADJUSTED": "Monthly Adjusted Time Series",
    }
    ts_key = key_map.get(function, "Time Series (Daily)")
    prices = data.get(ts_key, {})

    # If date filters are passed, apply them
    start_date = kwargs.get("start_date")
    end_date = kwargs.get("end_date")
    if (start_date or end_date) and prices:
        df = prices_to_df(prices)
        if not df.empty:
            if start_date:
                df = df[df.index >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df.index <= pd.to_datetime(end_date)]
            return df.to_dict(orient="index")
    return prices


def prices_to_df(prices: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert Alpha Vantage price dict into pandas DataFrame.
    """
    if not prices:
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(prices, orient="index")
    df.index = pd.to_datetime(df.index)
    df = df.rename(
        columns={
            "1. open": "open",
            "2. high": "high",
            "3. low": "low",
            "4. close": "close",
            "5. adjusted close": "adj_close",
            "6. volume": "volume",
        }
    )
    df = df.apply(pd.to_numeric, errors="coerce")
    return df.sort_index()


# ---------------------------
# Fundamentals
# ---------------------------
def get_company_overview(symbol: str) -> dict:
    return _alpha_vantage_request({"function": "OVERVIEW", "symbol": symbol})


def get_financial_metrics(symbol: str, *args, **kwargs) -> dict:
    """
    Returns key financial metrics from Alpha Vantage.
    Accepts extra kwargs (end_date, period, limit, api_key) for compatibility.
    """
    overview = get_company_overview(symbol)
    if not overview:
        return {}

    return {
        "symbol": overview.get("Symbol"),
        "name": overview.get("Name"),
        "sector": overview.get("Sector"),
        "industry": overview.get("Industry"),
        "market_cap": overview.get("MarketCapitalization"),
        "pe_ratio": overview.get("PERatio"),
        "peg_ratio": overview.get("PEGRatio"),
        "eps": overview.get("EPS"),
        "roe": overview.get("ReturnOnEquityTTM"),
        "profit_margin": overview.get("ProfitMargin"),
        "dividend_yield": overview.get("DividendYield"),
    }


def get_market_cap(symbol: str, *args, **kwargs) -> float:
    """
    Returns market capitalization as float.
    Extra args (end_date, api_key) are ignored for compatibility.
    """
    overview = get_company_overview(symbol)
    try:
        return float(overview.get("MarketCapitalization", 0))
    except Exception:
        return 0.0


def search_line_items(financials: dict, keyword: str) -> dict:
    """
    Search through financial metrics for keys that match the given keyword.

    Args:
        financials (dict): Dictionary of financial metrics (from get_financial_metrics).
        keyword (str): The keyword to search for, e.g. "revenue", "earnings".

    Returns:
        dict: Matching key-value pairs.
    """
    keyword_lower = keyword.lower()
    matches = {}
    for key, value in financials.items():
        if keyword_lower in key.lower():
            matches[key] = value
    return matches



# ---------------------------
# Placeholders (unsupported in Alpha Vantage)
# ---------------------------
def get_insider_trades(symbol: str, *args, **kwargs):
    """
    Placeholder - Alpha Vantage does not provide insider trades.
    Accepts extra kwargs (start_date, end_date, limit, api_key) for compatibility.
    """
    logger.warning("get_insider_trades: Not available via Alpha Vantage")
    return []


def get_company_news(symbol: str, *args, **kwargs):
    """
    Placeholder - Alpha Vantage does not provide company news.
    Accepts extra kwargs (start_date, end_date, limit, api_key) for compatibility.
    """
    logger.warning("get_company_news: Not available via Alpha Vantage")
    return []