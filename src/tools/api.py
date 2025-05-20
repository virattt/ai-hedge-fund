import datetime
import os
import pandas as pd
import requests

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    LineItem,
    Price,
    InsiderTrade,
)

# Global cache instance
_cache = get_cache()


def _polygon_get(url: str, params: dict | None = None) -> dict:
    """Helper to GET data from Polygon with API key."""
    if params is None:
        params = {}
    if api_key := os.environ.get("POLYGON_API_KEY"):
        params["apiKey"] = api_key
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {response.status_code} - {response.text}")
    return response.json()


def _to_numeric(value):
    """Return numeric value from polygon field which may be a dict."""
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch price data from cache or API."""
    # Check cache first
    if cached_data := _cache.get_prices(ticker):
        # Filter cached data by date range and convert to Price objects
        filtered_data = [Price(**price) for price in cached_data if start_date <= price["time"] <= end_date]
        if filtered_data:
            return filtered_data

    # If not in cache or no data in range, fetch from Polygon
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
    data = _polygon_get(url, {"adjusted": "true", "sort": "asc"})
    results = data.get("results", [])
    prices = [
        Price(
            open=r["o"],
            close=r["c"],
            high=r["h"],
            low=r["l"],
            volume=r["v"],
            time=datetime.datetime.utcfromtimestamp(r["t"] / 1000).strftime("%Y-%m-%d"),
        )
        for r in results
    ]

    if not prices:
        return []

    # Cache the results as dicts
    if prices:
        _cache.set_prices(ticker, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or API."""
    # Check cache first
    if cached_data := _cache.get_financial_metrics(ticker):
        # Filter cached data by date and limit
        filtered_data = [FinancialMetrics(**metric) for metric in cached_data if metric["report_period"] <= end_date]
        filtered_data.sort(key=lambda x: x.report_period, reverse=True)
        if filtered_data:
            return filtered_data[:limit]

    # If not in cache or insufficient data, fetch from Polygon
    timeframe = "annual" if period in ("ttm", "annual") else "quarterly"
    params = {
        "ticker": ticker,
        "timeframe": timeframe,
        "order": "desc",
        "limit": limit,
        "reportPeriod.lte": end_date,
    }
    data = _polygon_get("https://api.polygon.io/vX/reference/financials", params)
    results = data.get("results", [])

    def _transform(result: dict) -> FinancialMetrics:
        fs = result.get("financials", {})
        inc = fs.get("income_statement", {})
        bal = fs.get("balance_sheet", {})
        cfs = fs.get("cash_flow_statement", {})

        revenue = _to_numeric(inc.get("revenue") or inc.get("revenues"))
        gross_profit = _to_numeric(inc.get("gross_profit"))
        operating_income = _to_numeric(inc.get("operating_income") or inc.get("operating_income_loss"))
        net_income = _to_numeric(inc.get("net_income") or inc.get("net_income_loss"))
        interest_expense = _to_numeric(inc.get("interest_expense"))
        ebit = _to_numeric(inc.get("ebit") or operating_income)

        total_assets = _to_numeric(bal.get("assets") or bal.get("total_assets"))
        total_liabilities = _to_numeric(bal.get("liabilities") or bal.get("total_liabilities"))
        equity = _to_numeric(bal.get("shareholder_equity") or bal.get("total_shareholder_equity") or bal.get("equity"))

        current_assets = _to_numeric(bal.get("current_assets"))
        current_liabilities = _to_numeric(bal.get("current_liabilities"))
        cash = _to_numeric(bal.get("cash_and_cash_equivalents"))

        ocf = _to_numeric(cfs.get("net_cash_flow_from_operating_activities") or cfs.get("operating_cash_flow"))
        capex = _to_numeric(cfs.get("capital_expenditure"))
        free_cash_flow = _to_numeric(cfs.get("free_cash_flow"))

        shares = _to_numeric(result.get("weighted_average_shares_outstanding") or result.get("shares_outstanding"))

        return FinancialMetrics(
            ticker=ticker,
            report_period=result.get("end_date") or result.get("period_of_report"),
            period=result.get("fiscal_period") or timeframe,
            currency=result.get("currency_code") or "USD",
            market_cap=None,
            enterprise_value=None,
            price_to_earnings_ratio=None,
            price_to_book_ratio=None,
            price_to_sales_ratio=None,
            enterprise_value_to_ebitda_ratio=None,
            enterprise_value_to_revenue_ratio=None,
            free_cash_flow_yield=None,
            peg_ratio=None,
            gross_margin=gross_profit / revenue if gross_profit and revenue else None,
            operating_margin=operating_income / revenue if operating_income and revenue else None,
            net_margin=net_income / revenue if net_income and revenue else None,
            return_on_equity=net_income / equity if net_income and equity else None,
            return_on_assets=net_income / total_assets if net_income and total_assets else None,
            return_on_invested_capital=None,
            asset_turnover=revenue / total_assets if revenue and total_assets else None,
            inventory_turnover=None,
            receivables_turnover=None,
            days_sales_outstanding=None,
            operating_cycle=None,
            working_capital_turnover=None,
            current_ratio=current_assets / current_liabilities if current_assets and current_liabilities else None,
            quick_ratio=None,
            cash_ratio=cash / current_liabilities if cash and current_liabilities else None,
            operating_cash_flow_ratio=ocf / current_liabilities if ocf and current_liabilities else None,
            debt_to_equity=total_liabilities / equity if total_liabilities and equity else None,
            debt_to_assets=total_liabilities / total_assets if total_liabilities and total_assets else None,
            interest_coverage=ebit / abs(interest_expense) if ebit and interest_expense else None,
            revenue_growth=None,
            earnings_growth=None,
            book_value_growth=None,
            earnings_per_share_growth=None,
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=None,
            earnings_per_share=net_income / shares if net_income and shares else None,
            book_value_per_share=equity / shares if equity and shares else None,
            free_cash_flow_per_share=free_cash_flow / shares if free_cash_flow and shares else None,
        )

    metrics_list = [_transform(r) for r in results]

    if metrics_list:
        _cache.set_financial_metrics(ticker, [m.model_dump() for m in metrics_list])
    return metrics_list


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    """Fetch specific line items using Polygon financials."""
    timeframe = "annual" if period in ("ttm", "annual") else "quarterly"
    params = {
        "ticker": ticker,
        "timeframe": timeframe,
        "order": "desc",
        "limit": limit,
        "reportPeriod.lte": end_date,
    }
    data = _polygon_get("https://api.polygon.io/vX/reference/financials", params)
    results = data.get("results", [])

    def _extract(fs: dict, res: dict, name: str) -> float | None:
        inc = fs.get("income_statement", {})
        bal = fs.get("balance_sheet", {})
        cfs = fs.get("cash_flow_statement", {})
        if name == "free_cash_flow":
            return _to_numeric(cfs.get("free_cash_flow"))
        if name == "ebit":
            return _to_numeric(inc.get("ebit") or inc.get("operating_income") or inc.get("operating_income_loss"))
        if name == "interest_expense":
            return _to_numeric(inc.get("interest_expense"))
        if name == "capital_expenditure":
            return _to_numeric(cfs.get("capital_expenditure"))
        if name == "depreciation_and_amortization":
            return _to_numeric(cfs.get("depreciation_and_amortization"))
        if name == "outstanding_shares":
            return _to_numeric(res.get("weighted_average_shares_outstanding") or res.get("shares_outstanding"))
        if name == "net_income":
            return _to_numeric(inc.get("net_income") or inc.get("net_income_loss"))
        if name == "revenue":
            return _to_numeric(inc.get("revenue") or inc.get("revenues"))
        if name == "working_capital":
            ca = _to_numeric(bal.get("current_assets"))
            cl = _to_numeric(bal.get("current_liabilities"))
            if ca is not None and cl is not None:
                return ca - cl
        if name == "total_debt":
            return _to_numeric(bal.get("total_debt") or bal.get("liabilities") or bal.get("total_liabilities"))
        return None

    line_item_results = []
    for result in results:
        fs = result.get("financials", {})
        values = {name: _extract(fs, result, name) for name in line_items}
        item = LineItem(
            ticker=ticker,
            report_period=result.get("end_date") or result.get("period_of_report"),
            period=result.get("fiscal_period") or timeframe,
            currency=result.get("currency_code") or "USD",
            **values,
        )
        line_item_results.append(item)

    return line_item_results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[InsiderTrade]:
    """Polygon does not provide insider trading data. Return an empty list."""
    return []


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[CompanyNews]:
    """Fetch company news from Polygon."""
    if cached_data := _cache.get_company_news(ticker):
        filtered = [CompanyNews(**n) for n in cached_data if (start_date is None or n["date"] >= start_date) and n["date"] <= end_date]
        filtered.sort(key=lambda x: x.date, reverse=True)
        if filtered:
            return filtered

    params = {
        "ticker": ticker,
        "order": "desc",
        "limit": limit,
        "published_utc.lte": end_date,
    }
    if start_date:
        params["published_utc.gte"] = start_date

    data = _polygon_get("https://api.polygon.io/v2/reference/news", params)
    results = data.get("results", [])
    news_list = [
        CompanyNews(
            ticker=ticker,
            title=n.get("title"),
            author=n.get("author"),
            source=n.get("source"),
            date=(n.get("published_utc") or "").split("T")[0],
            url=n.get("article_url"),
        )
        for n in results
    ]

    if news_list:
        _cache.set_company_news(ticker, [n.model_dump() for n in news_list])
    return news_list


def get_market_cap(
    ticker: str,
    end_date: str,
) -> float | None:
    """Fetch market cap using Polygon ticker details."""
    data = _polygon_get(f"https://api.polygon.io/v3/reference/tickers/{ticker}")
    details = data.get("results", {}) if isinstance(data, dict) else {}
    market_cap = details.get("market_cap")
    if market_cap:
        return market_cap

    shares = details.get("share_class_shares_outstanding") or details.get("weighted_shares_outstanding") or details.get("shares_outstanding")
    if not shares:
        return None

    prices = get_prices(ticker, end_date, end_date)
    price = prices[-1].close if prices else None
    if price is None:
        return None
    return shares * price


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
