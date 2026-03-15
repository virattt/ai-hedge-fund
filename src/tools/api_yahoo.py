"""Yahoo Finance provider for financial data.

Uses the yfinance library (free, no API key required).
Install: poetry add yfinance

Limitations vs Financial Datasets:
- Insider trades only covers recent ~90 days
- search_line_items covers income/balance/cash flow statements only
- News articles do not include sentiment scores
- Historical financial metrics are approximated from statement data;
  ratio fields that require intraday price snapshots are taken from
  the current info dict and applied to all historical periods.
"""

import datetime
import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)

_cache = get_cache()

# ---------------------------------------------------------------------------
# yfinance row-label mappings for search_line_items
# ---------------------------------------------------------------------------
_YF_INCOME: dict[str, list[str]] = {
    "revenue": ["Total Revenue", "Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "EBIT"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "research_and_development": ["Research And Development"],
    "selling_general_and_administrative": ["Selling General And Administration"],
    "depreciation_and_amortization": ["Reconciled Depreciation"],
    "interest_expense": ["Interest Expense", "Interest Expense Non Operating"],
    "income_tax_expense": ["Tax Provision"],
}

_YF_BALANCE: dict[str, list[str]] = {
    "total_assets": ["Total Assets"],
    "total_liabilities": ["Total Liabilities Net Minority Interest"],
    "shareholders_equity": ["Stockholders Equity", "Common Stock Equity"],
    "cash_and_equivalents": ["Cash And Cash Equivalents"],
    "total_debt": ["Total Debt"],
    "net_debt": ["Net Debt"],
    "accounts_receivable": ["Accounts Receivable", "Net Receivables"],
    "inventory": ["Inventory"],
    "accounts_payable": ["Accounts Payable"],
    "goodwill": ["Goodwill"],
    "total_current_assets": ["Current Assets"],
    "total_current_liabilities": ["Current Liabilities"],
    "long_term_debt": ["Long Term Debt"],
}

_YF_CASHFLOW: dict[str, list[str]] = {
    "operating_cash_flow": ["Operating Cash Flow"],
    "capital_expenditure": ["Capital Expenditure"],
    "free_cash_flow": ["Free Cash Flow"],
    "dividends_paid": ["Payment Of Dividends"],
    "depreciation_and_amortization": ["Depreciation And Amortization", "Depreciation Amortization Depletion"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _ticker(symbol: str):
    """Return a yfinance Ticker object (lazy import so yfinance is optional)."""
    import yfinance as yf

    return yf.Ticker(symbol)


# ---------------------------------------------------------------------------
# get_prices
# ---------------------------------------------------------------------------
def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    cache_key = f"{ticker}_{start_date}_{end_date}"
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**p) for p in cached_data]

    try:
        t = _ticker(ticker)
        df = t.history(start=start_date, end=end_date, auto_adjust=True)
        if df.empty:
            return []

        prices = [
            Price(
                open=float(row["Open"]),
                close=float(row["Close"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                volume=int(row["Volume"]),
                time=date.strftime("%Y-%m-%d"),
            )
            for date, row in df.iterrows()
        ]

        _cache.set_prices(cache_key, [p.model_dump() for p in prices])
        return prices
    except Exception as e:
        logger.warning("Yahoo Finance: failed to fetch prices for %s: %s", ticker, e)
        return []


# ---------------------------------------------------------------------------
# get_financial_metrics
# ---------------------------------------------------------------------------
def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**m) for m in cached_data]

    try:
        t = _ticker(ticker)
        info = t.info or {}

        if period == "ttm":
            metrics = [_build_ttm_metrics(ticker, end_date, info)]
        else:
            metrics = _build_historical_metrics(ticker, end_date, period, limit, t, info)

        if not metrics:
            return []

        _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics])
        return metrics
    except Exception as e:
        logger.warning("Yahoo Finance: failed to fetch financial metrics for %s: %s", ticker, e)
        return []


def _build_ttm_metrics(ticker: str, report_period: str, info: dict) -> FinancialMetrics:
    market_cap = _safe_float(info.get("marketCap"))
    ev = _safe_float(info.get("enterpriseValue"))
    revenue = _safe_float(info.get("totalRevenue"))
    ebitda = _safe_float(info.get("ebitda"))
    fcf = _safe_float(info.get("freeCashflow"))
    shares = _safe_float(info.get("sharesOutstanding"))

    de = _safe_float(info.get("debtToEquity"))
    if de is not None:
        de = de / 100  # yfinance reports as percentage (e.g. 150 → 1.5×)

    return FinancialMetrics(
        ticker=ticker,
        report_period=report_period,
        period="ttm",
        currency=info.get("currency", "USD"),
        market_cap=market_cap,
        enterprise_value=ev,
        price_to_earnings_ratio=_safe_float(info.get("trailingPE")),
        price_to_book_ratio=_safe_float(info.get("priceToBook")),
        price_to_sales_ratio=_safe_float(info.get("priceToSalesTrailing12Months")),
        enterprise_value_to_ebitda_ratio=(ev / ebitda) if (ev and ebitda) else _safe_float(info.get("enterpriseToEbitda")),
        enterprise_value_to_revenue_ratio=(ev / revenue) if (ev and revenue) else _safe_float(info.get("enterpriseToRevenue")),
        free_cash_flow_yield=(fcf / market_cap) if (fcf and market_cap) else None,
        peg_ratio=_safe_float(info.get("pegRatio")),
        gross_margin=_safe_float(info.get("grossMargins")),
        operating_margin=_safe_float(info.get("operatingMargins")),
        net_margin=_safe_float(info.get("profitMargins")),
        return_on_equity=_safe_float(info.get("returnOnEquity")),
        return_on_assets=_safe_float(info.get("returnOnAssets")),
        return_on_invested_capital=None,
        asset_turnover=None,
        inventory_turnover=None,
        receivables_turnover=None,
        days_sales_outstanding=None,
        operating_cycle=None,
        working_capital_turnover=None,
        current_ratio=_safe_float(info.get("currentRatio")),
        quick_ratio=_safe_float(info.get("quickRatio")),
        cash_ratio=None,
        operating_cash_flow_ratio=None,
        debt_to_equity=de,
        debt_to_assets=None,
        interest_coverage=None,
        revenue_growth=_safe_float(info.get("revenueGrowth")),
        earnings_growth=_safe_float(info.get("earningsGrowth")),
        book_value_growth=None,
        earnings_per_share_growth=None,
        free_cash_flow_growth=None,
        operating_income_growth=None,
        ebitda_growth=None,
        payout_ratio=_safe_float(info.get("payoutRatio")),
        earnings_per_share=_safe_float(info.get("trailingEps")),
        book_value_per_share=_safe_float(info.get("bookValue")),
        free_cash_flow_per_share=(fcf / shares) if (fcf and shares) else None,
    )


def _build_historical_metrics(ticker: str, end_date: str, period: str, limit: int, t, info: dict) -> list[FinancialMetrics]:
    try:
        if period == "annual":
            fin, bs, cf = t.financials, t.balance_sheet, t.cashflow
        else:
            fin, bs, cf = t.quarterly_financials, t.quarterly_balance_sheet, t.quarterly_cashflow
    except Exception:
        return []

    if fin is None or fin.empty:
        return []

    dates = sorted([col for col in fin.columns if str(col)[:10] <= end_date], reverse=True)[:limit]
    if not dates:
        return []

    def _row(df, labels: list[str]) -> dict:
        if df is None or df.empty:
            return {}
        for label in labels:
            if label in df.index:
                return {str(col)[:10]: _safe_float(df.loc[label, col]) for col in df.columns}
        return {}

    rev_map = _row(fin, ["Total Revenue"])
    ni_map = _row(fin, ["Net Income", "Net Income Common Stockholders"])
    assets_map = _row(bs, ["Total Assets"])
    equity_map = _row(bs, ["Stockholders Equity", "Common Stock Equity"])
    ocf_map = _row(cf, ["Operating Cash Flow"])
    capex_map = _row(cf, ["Capital Expenditure"])

    market_cap = _safe_float(info.get("marketCap"))
    raw_de = _safe_float(info.get("debtToEquity"))
    de_normalized = (raw_de / 100) if raw_de is not None else None  # yfinance reports as % (150 → 1.5×)
    results = []
    for date in dates:
        d = str(date)[:10]
        revenue = rev_map.get(d)
        net_income = ni_map.get(d)
        total_assets = assets_map.get(d)
        total_equity = equity_map.get(d)
        ocf = ocf_map.get(d)
        capex = capex_map.get(d)
        fcf = (ocf + capex) if (ocf is not None and capex is not None) else None

        results.append(
            FinancialMetrics(
                ticker=ticker,
                report_period=d,
                period=period,
                currency=info.get("currency", "USD"),
                market_cap=market_cap,
                enterprise_value=_safe_float(info.get("enterpriseValue")),
                price_to_earnings_ratio=_safe_float(info.get("trailingPE")),
                price_to_book_ratio=_safe_float(info.get("priceToBook")),
                price_to_sales_ratio=_safe_float(info.get("priceToSalesTrailing12Months")),
                enterprise_value_to_ebitda_ratio=_safe_float(info.get("enterpriseToEbitda")),
                enterprise_value_to_revenue_ratio=_safe_float(info.get("enterpriseToRevenue")),
                free_cash_flow_yield=(fcf / market_cap) if (fcf and market_cap) else None,
                peg_ratio=_safe_float(info.get("pegRatio")),
                gross_margin=_safe_float(info.get("grossMargins")),
                operating_margin=_safe_float(info.get("operatingMargins")),
                net_margin=(net_income / revenue) if (net_income and revenue) else None,
                return_on_equity=(net_income / total_equity) if (net_income and total_equity) else None,
                return_on_assets=(net_income / total_assets) if (net_income and total_assets) else None,
                return_on_invested_capital=None,
                asset_turnover=None,
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                current_ratio=_safe_float(info.get("currentRatio")),
                quick_ratio=_safe_float(info.get("quickRatio")),
                cash_ratio=None,
                operating_cash_flow_ratio=None,
                debt_to_equity=de_normalized,
                debt_to_assets=None,
                interest_coverage=None,
                revenue_growth=_safe_float(info.get("revenueGrowth")),
                earnings_growth=_safe_float(info.get("earningsGrowth")),
                book_value_growth=None,
                earnings_per_share_growth=None,
                free_cash_flow_growth=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=_safe_float(info.get("payoutRatio")),
                earnings_per_share=_safe_float(info.get("trailingEps")),
                book_value_per_share=_safe_float(info.get("bookValue")),
                free_cash_flow_per_share=None,
            )
        )

    return results


# ---------------------------------------------------------------------------
# search_line_items
# ---------------------------------------------------------------------------
def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    try:
        t = _ticker(ticker)
        info = t.info or {}

        if period in ("ttm", "annual"):
            fin, bs, cf = t.financials, t.balance_sheet, t.cashflow
        else:
            fin, bs, cf = t.quarterly_financials, t.quarterly_balance_sheet, t.quarterly_cashflow

        # Build a lookup: our_name → (DataFrame, row_label)
        frame_lookup: dict[str, tuple] = {}
        for df, mapping in [(fin, _YF_INCOME), (bs, _YF_BALANCE), (cf, _YF_CASHFLOW)]:
            if df is None or df.empty:
                continue
            for our_name, yf_labels in mapping.items():
                if our_name in frame_lookup:
                    continue
                for label in yf_labels:
                    if label in df.index:
                        frame_lookup[our_name] = (df, label)
                        break

        # Determine date columns
        ref_df = next((df for df in [fin, bs, cf] if df is not None and not df.empty), None)
        if ref_df is not None:
            dates = sorted([col for col in ref_df.columns if str(col)[:10] <= end_date], reverse=True)[:limit]
        else:
            dates = [end_date]

        if not dates:
            return []

        results = []
        for date in dates:
            date_str = str(date)[:10]
            data: dict = {
                "ticker": ticker,
                "report_period": date_str,
                "period": period,
                "currency": info.get("currency", "USD"),
            }
            for item in line_items:
                if item in frame_lookup:
                    df, label = frame_lookup[item]
                    try:
                        data[item] = _safe_float(df.loc[label, date])
                    except (KeyError, Exception):
                        data[item] = None
                else:
                    data[item] = None
            results.append(LineItem(**data))

        return results[:limit]
    except Exception as e:
        logger.warning("Yahoo Finance: failed to fetch line items for %s: %s", ticker, e)
        return []


# ---------------------------------------------------------------------------
# get_insider_trades
# ---------------------------------------------------------------------------
def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    try:
        t = _ticker(ticker)
        df = t.insider_transactions
        if df is None or df.empty:
            return []

        df.columns = [str(c).strip() for c in df.columns]

        trades = []
        for _, row in df.iterrows():
            filing_date = str(row.get("Start Date") or row.get("Date") or "")[:10]
            if not filing_date:
                continue
            if filing_date > end_date:
                continue
            if start_date and filing_date < start_date:
                continue

            shares = _safe_float(row.get("Shares") or row.get("Transaction Shares"))
            value = _safe_float(row.get("Value") or row.get("Transaction Value"))
            price_per = (value / shares) if (value and shares and shares != 0) else None

            trades.append(
                InsiderTrade(
                    ticker=ticker,
                    issuer=ticker,
                    name=str(row.get("Insider") or row.get("Name") or ""),
                    title=str(row.get("Position") or row.get("Title") or ""),
                    is_board_director=None,
                    transaction_date=filing_date,
                    transaction_shares=shares,
                    transaction_price_per_share=price_per,
                    transaction_value=value,
                    shares_owned_before_transaction=None,
                    shares_owned_after_transaction=_safe_float(row.get("Shares Total") or row.get("Shares Owned")),
                    security_title=str(row.get("Text") or row.get("Transaction") or "")[:100] or None,
                    filing_date=filing_date,
                )
            )

            if len(trades) >= limit:
                break

        if trades:
            _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in trades])
        return trades
    except Exception as e:
        logger.warning("Yahoo Finance: failed to fetch insider trades for %s: %s", ticker, e)
        return []


# ---------------------------------------------------------------------------
# get_company_news
# ---------------------------------------------------------------------------
def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    try:
        t = _ticker(ticker)
        raw_news = t.news or []

        news_items = []
        for item in raw_news:
            ts = item.get("providerPublishTime") or item.get("publishTime")
            date_str = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d") if ts else end_date

            if date_str > end_date:
                continue
            if start_date and date_str < start_date:
                continue

            news_items.append(
                CompanyNews(
                    ticker=ticker,
                    title=item.get("title", ""),
                    author="",
                    source=item.get("publisher") or item.get("source") or "",
                    date=date_str,
                    url=item.get("link") or item.get("url") or "",
                    sentiment=None,
                )
            )

            if len(news_items) >= limit:
                break

        if news_items:
            _cache.set_company_news(cache_key, [n.model_dump() for n in news_items])
        return news_items
    except Exception as e:
        logger.warning("Yahoo Finance: failed to fetch news for %s: %s", ticker, e)
        return []


# ---------------------------------------------------------------------------
# get_market_cap
# ---------------------------------------------------------------------------
def get_market_cap(ticker: str, end_date: str, api_key: str = None) -> float | None:
    try:
        return _safe_float(_ticker(ticker).info.get("marketCap"))
    except Exception as e:
        logger.warning("Yahoo Finance: failed to fetch market cap for %s: %s", ticker, e)
        return None


# ---------------------------------------------------------------------------
# Utilities (identical across providers)
# ---------------------------------------------------------------------------
def prices_to_df(prices: list[Price]) -> pd.DataFrame:
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
