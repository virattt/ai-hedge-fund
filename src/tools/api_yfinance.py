import datetime
import logging
import re
from datetime import datetime as dt
from typing import Optional

import pandas as pd
import yfinance as yf

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)

logger = logging.getLogger(__name__)

_cache = get_cache()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _none(v):
    """Return None if v is NaN/None, otherwise return v."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


# ---------------------------------------------------------------------------
# get_prices
# ---------------------------------------------------------------------------

def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """
    Fetch daily OHLCV price data via yfinance.
    """
    cache_key = f"{ticker}_{start_date}_{end_date}"
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**p) for p in cached_data]

    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
    except Exception as e:
        logger.warning("yfinance download failed for %s [%s-%s]: %s", ticker, start_date, end_date, e)
        return []

    if df.empty:
        return []

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    prices = []
    for dt_idx, row in df.iterrows():
        date_str = str(dt_idx.date()) if hasattr(dt_idx, "date") else str(dt_idx)[:10]
        prices.append(Price(
            open=float(row["Open"]),
            close=float(row["Close"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            volume=int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
            time=date_str,
        ))

    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


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
    """
    Fetch financial metrics via yfinance Ticker.info (single snapshot).
    """
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**m) for m in cached_data]

    try:
        info = yf.Ticker(ticker).info
    except Exception as e:
        logger.warning("yfinance info failed for %s: %s", ticker, e)
        return []

    if not info or info.get("regularMarketPrice") is None:
        return []

    i = info

    def g(k, default=None):
        return _none(i.get(k, default))

    metrics = FinancialMetrics(
        ticker=ticker,
        report_period=end_date,
        period=period,
        currency="USD",
        # Valuation
        market_cap=g("marketCap"),
        enterprise_value=g("enterpriseValue"),
        price_to_earnings_ratio=g("trailingPE"),
        price_to_book_ratio=g("priceToBook"),
        price_to_sales_ratio=g("priceToSalesTrailing12Months"),
        enterprise_value_to_ebitda_ratio=g("enterpriseToEbitda"),
        enterprise_value_to_revenue_ratio=g("enterpriseToRevenue"),
        free_cash_flow_yield=g("freeCashflowYield"),
        peg_ratio=g("pegRatio"),
        # Profitability margins
        gross_margin=g("grossMargin"),
        operating_margin=g("operatingMargin"),
        net_margin=g("profitMargins"),
        # Returns
        return_on_equity=g("returnOnEquity"),
        return_on_assets=g("returnOnAssets"),
        return_on_invested_capital=g("investedCapital"),
        # Efficiency
        asset_turnover=g("assetTurnover"),
        inventory_turnover=g("inventoryTurnover"),
        receivables_turnover=g("receivablesTurnover"),
        days_sales_outstanding=g("daysOfSalesOutstanding"),
        operating_cycle=g("operatingCycle"),
        working_capital_turnover=g("workingCapitalTurnover"),
        # Liquidity
        current_ratio=g("currentRatio"),
        quick_ratio=g("quickRatio"),
        cash_ratio=g("cashRatio"),
        operating_cash_flow_ratio=g("operatingCashflowRatio"),
        # Leverage
        debt_to_equity=g("debtToEquity"),
        debt_to_assets=g("debtToAssets"),
        interest_coverage=g("interestCoverage"),
        # Growth
        revenue_growth=g("revenueGrowth"),
        earnings_growth=g("earningsGrowth"),
        book_value_growth=g("bookValueGrowth"),
        earnings_per_share_growth=g("earningsGrowth"),
        free_cash_flow_growth=None,
        operating_income_growth=g("operatingIncomeGrowth"),
        ebitda_growth=g("ebitdaGrowth"),
        # Per-share
        payout_ratio=g("payoutRatio"),
        earnings_per_share=g("trailingEps"),
        book_value_per_share=g("bookValue"),
        free_cash_flow_per_share=(
            g("freeCashflow") / g("sharesOutstanding")
            if g("freeCashflow") and g("sharesOutstanding")
            else None
        ),
    )

    _cache.set_financial_metrics(cache_key, [metrics.model_dump()])
    return [metrics]


# ---------------------------------------------------------------------------
# search_line_items
# ---------------------------------------------------------------------------

# Mapping from agent-expected field names → (statement_type, yfinance_row_name)
_LINE_ITEM_MAP = {
    # Income statement
    "revenue":                     ("income_stmt", "Total Revenue"),
    "net_income":                  ("income_stmt", "Net Income"),
    "gross_profit":                ("income_stmt", "Gross Profit"),
    "operating_income":             ("income_stmt", "Operating Income"),
    "ebitda":                      ("income_stmt", "EBITDA"),
    "ebit":                        ("income_stmt", "EBIT"),
    "interest_expense":             ("income_stmt", "Interest Expense"),
    "basic_eps":                   ("income_stmt", "Basic EPS"),
    "diluted_eps":                 ("income_stmt", "Diluted EPS"),
    "earnings_per_share":           ("income_stmt", "Basic EPS"),
    "book_value_per_share":        ("income_stmt", "Basic EPS"),  # fallback, overridden below
    "research_and_development":    ("income_stmt", "Research And Development"),
    "selling_general_and_admin":   ("income_stmt", "Selling, General & Admin."),
    "operating_expense":           ("income_stmt", "Operating Expense"),
    "cost_of_revenue":             ("income_stmt", "Cost Of Revenue"),
    # Balance sheet
    "total_assets":                ("balance_sheet", "Total Assets"),
    "total_liabilities":           ("balance_sheet", "Total Liabilities Net Minority Interest"),
    "total_equity":                ("balance_sheet", "Stockholders Equity"),
    "shareholders_equity":           ("balance_sheet", "Stockholders Equity"),
    "current_assets":               ("balance_sheet", "Current Assets"),
    "current_liabilities":          ("balance_sheet", "Current Liabilities"),
    "cash_and_cash_equivalents":   ("balance_sheet", "Cash And Cash Equivalents"),
    "cash_and_equivalents":        ("balance_sheet", "Cash And Cash Equivalents"),
    "long_term_debt":              ("balance_sheet", "Long Term Debt"),
    "short_term_debt":             ("balance_sheet", "Current Debt And Capital Lease Obligation"),
    "inventory":                   ("balance_sheet", "Inventory"),
    "accounts_receivable":         ("balance_sheet", "Accounts Receivable"),
    "accounts_payable":            ("balance_sheet", "Payables And Accrued Expenses"),
    "goodwill":                    ("balance_sheet", "Goodwill And Other Intangible Assets"),
    "intangible_assets":           ("balance_sheet", "Other Intangible Assets"),
    "property_plant_and_equipment":("balance_sheet", "Net PPE"),
    "total_debt":                  ("balance_sheet", "Total Debt"),
    "net_debt":                    ("balance_sheet", "Net Debt"),
    # Cash flow
    "operating_cash_flow":         ("cashflow", "Operating Cash Flow"),
    "free_cash_flow":              ("cashflow", "Free Cash Flow"),
    "capital_expenditures":        ("cashflow", "Capital Expenditure"),
    "capital_expenditure":         ("cashflow", "Capital Expenditure"),
    "dividends_paid":              ("cashflow", "Cash Dividends Paid"),
    "debt_repayment":              ("cashflow", "Repayment Of Debt"),
    "share_repurchases":           ("cashflow", "Repurchase Of Capital Stock"),
    "cash_flow_from_financing":    ("cashflow", "Financing Cash Flow"),
    "cash_flow_from_investing":    ("cashflow", "Investing Cash Flow"),
    "cash_flow_from_operations":   ("cashflow", "Cash Flow From Operations"),
    "effect_of_exchange_rate":     ("cashflow", "Effect Of Exchange Rate Changes"),
    "depreciation_and_amortization":("cashflow", "Depreciation And Amortization"),
}

# Fields computed from other line items or info (not directly from yfinance rows)
_DERIVED_FIELDS = {
    "operating_margin",
    "debt_to_equity",
    "dividends_and_other_cash_distributions",
    "outstanding_shares",
    "gross_margin",
}


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """
    Fetch specific line items from yfinance financial statements.
    Returns up to `limit` records per report period.
    """
    ticker_obj = yf.Ticker(ticker)

    try:
        income = ticker_obj.financials
    except Exception as e:
        logger.warning("yfinance financials failed for %s: %s", ticker, e)
        income = pd.DataFrame()
    try:
        balance = ticker_obj.balance_sheet
    except Exception as e:
        logger.warning("yfinance balance_sheet failed for %s: %s", ticker, e)
        balance = pd.DataFrame()
    try:
        cashflow = ticker_obj.cashflow
    except Exception as e:
        logger.warning("yfinance cashflow failed for %s: %s", ticker, e)
        cashflow = pd.DataFrame()

    if income.empty and balance.empty and cashflow.empty:
        return []

    dfs = {"income_stmt": income, "balance_sheet": balance, "cashflow": cashflow}

    # Determine which canonical items we can satisfy from yfinance
    requested_derived = set()
    resolved_items = []
    for item in line_items:
        key = item.lower()
        if key in _LINE_ITEM_MAP:
            resolved_items.append((item, _LINE_ITEM_MAP[key]))
        elif key in _DERIVED_FIELDS:
            requested_derived.add(key)
            # Ensure dependencies are fetched
            if key == "operating_margin":
                for dep in ["operating_income", "revenue", "gross_profit"]:
                    dep_key = dep.lower()
                    if dep_key in _LINE_ITEM_MAP and not any(
                        r[0].lower() == dep_key for r in resolved_items
                    ):
                        resolved_items.append((dep, _LINE_ITEM_MAP[dep_key]))
            elif key == "gross_margin":
                for dep in ["gross_profit", "revenue"]:
                    dep_key = dep.lower()
                    if dep_key in _LINE_ITEM_MAP and not any(
                        r[0].lower() == dep_key for r in resolved_items
                    ):
                        resolved_items.append((dep, _LINE_ITEM_MAP[dep_key]))
            elif key == "debt_to_equity":
                for dep in ["total_debt", "total_equity"]:
                    dep_key = dep.lower()
                    if dep_key in _LINE_ITEM_MAP and not any(
                        r[0].lower() == dep_key for r in resolved_items
                    ):
                        resolved_items.append((dep, _LINE_ITEM_MAP[dep_key]))
            elif key == "dividends_and_other_cash_distributions":
                dep = "dividends_paid"
                dep_key = dep.lower()
                if dep_key in _LINE_ITEM_MAP and not any(
                    r[0].lower() == dep_key for r in resolved_items
                ):
                    resolved_items.append((dep, _LINE_ITEM_MAP[dep_key]))
        else:
            # Try exact yfinance row name match
            for _, (_, yf_name) in _LINE_ITEM_MAP.items():
                if yf_name.lower() == key:
                    resolved_items.append((item, _LINE_ITEM_MAP[yf_name.lower()]))
                    break

    if not resolved_items and not requested_derived:
        return []

    # Collect all report periods across the three DataFrames
    all_periods = set()
    for df_name, df in dfs.items():
        if not df.empty:
            all_periods.update(str(c) for c in df.columns)

    sorted_periods = sorted(all_periods, reverse=True)[:limit]
    if not sorted_periods:
        return []

    # Pre-fetch ticker info for derived fields that need it
    ticker_info = {}
    try:
        ticker_info = yf.Ticker(ticker).info
    except Exception:
        pass

    # All fields that any agent might directly access (safelist)
    _ALL_AGENT_FIELDS = {
        "capital_expenditure", "depreciation_and_amortization", "net_income",
        "outstanding_shares", "total_assets", "total_liabilities",
        "shareholders_equity", "total_equity", "dividends_and_other_cash_distributions",
        "gross_profit", "revenue", "free_cash_flow", "working_capital",
        "current_assets", "current_liabilities", "operating_expense",
        "selling_general_and_admin", "research_and_development",
        "interest_expense", "income_tax", "ebitda", "ebit",
        "cash_and_equivalents", "cash_and_cash_equivalents",
        "short_term_debt", "long_term_debt", "total_debt", "net_debt",
        "goodwill", "intangible_assets", "property_plant_and_equipment",
        "accounts_receivable", "accounts_payable", "inventory",
        "basic_eps", "diluted_eps", "earnings_per_share", "book_value_per_share",
        "operating_income", "operating_margin", "gross_margin",
        "debt_to_equity", "dividends_paid",
        "share_repurchases", "debt_repayment",
        "capital_expenditures",
        "operating_cash_flow", "cash_flow_from_operations",
        "cash_flow_from_financing", "cash_flow_from_investing",
        "effect_of_exchange_rate",
        "net_income_from_continuing_operations",
    }

    results: list[LineItem] = []
    for period_str in sorted_periods:
        extra = {}
        # Pre-populate all fields that agents might access to avoid AttributeError
        for canonical_name, _ in resolved_items:
            extra[canonical_name] = None
        for canonical_name in requested_derived:
            extra[canonical_name] = None
        for field in _ALL_AGENT_FIELDS:
            if field not in extra:
                extra[field] = None

        for canonical_name, (df_name, yf_name) in resolved_items:
            df = dfs.get(df_name)
            if df is None or df.empty:
                continue
            try:
                # Find the row by bidirectional fuzzy match
                matched_idx = None
                for idx in df.index:
                    idx_lower = str(idx).lower()
                    yf_lower = yf_name.lower()
                    if yf_lower in idx_lower or idx_lower in yf_lower:
                        matched_idx = idx
                        break
                if matched_idx is None:
                    continue
                # Find the column by date substring match
                matched_col = None
                for col in df.columns:
                    if period_str in str(col):
                        matched_col = col
                        break
                if matched_col is None:
                    continue
                val = df.loc[matched_idx, matched_col]
                if pd.notna(val):
                    extra[canonical_name] = float(val)
            except Exception:
                continue

        # Compute derived fields
        if extra.get("operating_margin") is None and extra.get("revenue") not in (None, 0):
            if extra.get("operating_income") is not None:
                extra["operating_margin"] = extra["operating_income"] / extra["revenue"]
            elif extra.get("gross_profit") is not None:
                extra["operating_margin"] = extra["gross_profit"] / extra["revenue"]

        if extra.get("gross_margin") is None and extra.get("revenue") not in (None, 0):
            gp = extra.get("gross_profit")
            if gp is not None:
                extra["gross_margin"] = gp / extra["revenue"]

        if extra.get("debt_to_equity") is None:
            td = extra.get("total_debt")
            te = extra.get("total_equity")
            if td and te and te != 0:
                extra["debt_to_equity"] = td / te

        if extra.get("dividends_and_other_cash_distributions") is None:
            dp = extra.get("dividends_paid")
            if dp is not None:
                extra["dividends_and_other_cash_distributions"] = abs(dp)

        if extra.get("outstanding_shares") is None:
            shares = ticker_info.get("sharesOutstanding")
            if shares:
                extra["outstanding_shares"] = shares

        # book_value_per_share override: use tangible book value / shares
        if extra.get("book_value_per_share") is None:
            tbv = extra.get("shareholders_equity") or extra.get("total_equity")
            shares = extra.get("outstanding_shares") or ticker_info.get("sharesOutstanding")
            if tbv and shares:
                extra["book_value_per_share"] = tbv / shares

        if extra:
            results.append(LineItem(
                ticker=ticker,
                report_period=period_str,
                period="annual" if "Q" not in period_str else "quarterly",
                currency="USD",
                **extra,
            ))

    return results[:limit]


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
    """
    Fetch insider transactions via yfinance Ticker.insider_transactions.
    """
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**t) for t in cached_data]

    try:
        transactions = yf.Ticker(ticker).insider_transactions
    except Exception as e:
        logger.warning("yfinance insider_transactions failed for %s: %s", ticker, e)
        return []

    if transactions is None or transactions.empty:
        return []

    if not pd.api.types.is_datetime64_any_dtype(transactions.index):
        try:
            transactions.index = pd.to_datetime(transactions.index)
        except Exception:
            pass

    results: list[InsiderTrade] = []
    for _, row in transactions.iterrows():
        start_date_raw = row.get("Start Date", "")
        filing_str = str(start_date_raw)[:10] if start_date_raw and pd.notna(start_date_raw) else ""
        txn_text = str(row.get("Text", "")) if pd.notna(row.get("Text")) else ""

        if end_date and filing_str > end_date:
            continue
        if start_date and filing_str < start_date:
            continue

        shares = _none(row.get("Shares"))
        value = _none(row.get("Value"))

        # Try to extract price from text like "Sale at price 255.12 - 255.82 per share."
        price = None
        price_match = re.search(r"price\s+([\d.]+)", txn_text)
        if price_match:
            try:
                price = float(price_match.group(1))
            except ValueError:
                pass

        results.append(InsiderTrade(
            ticker=ticker,
            issuer=ticker,
            name=_none(row.get("Insider")),
            title=_none(row.get("Position")),
            is_board_director=None,
            transaction_date=filing_str,
            transaction_shares=shares,
            transaction_price_per_share=price,
            transaction_value=value,
            shares_owned_before_transaction=None,
            shares_owned_after_transaction=None,
            security_title=_none(row.get("Ownership")),
            filing_date=filing_str,
        ))

        if len(results) >= limit:
            break

    _cache.set_insider_trades(cache_key, [r.model_dump() for r in results])
    return results


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
    """
    Fetch company news via yfinance Ticker.news.
    """
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**n) for n in cached_data]

    try:
        news_list = yf.Ticker(ticker).news
    except Exception as e:
        logger.warning("yfinance news failed for %s: %s", ticker, e)
        return []

    if not news_list:
        return []

    end_dt = None
    start_dt = None
    try:
        end_dt = pd.to_datetime(end_date, utc=True)
        if start_date:
            start_dt = pd.to_datetime(start_date, utc=True)
    except Exception:
        pass

    results: list[CompanyNews] = []
    for item in news_list:
        content = item.get("content", item)
        title = content.get("title", item.get("title", ""))
        if not title:
            continue

        pub_date_str = content.get("pubDate") or content.get("displayTime") or ""
        if pub_date_str:
            try:
                pub_dt = pd.to_datetime(pub_date_str, utc=True)
                date_str = str(pub_dt.date())
            except Exception:
                date_str = str(pub_date_str)[:10]
        else:
            pub_time = item.get("providerPublishTime")
            if pub_time is None:
                continue
            try:
                pub_dt = pd.to_datetime(pub_time, unit="s" if isinstance(pub_time, (int, float)) else None, utc=True)
                date_str = str(pub_dt.date())
            except Exception:
                continue

        try:
            if end_dt and pd.to_datetime(date_str, utc=True) > end_dt:
                continue
            if start_dt and pd.to_datetime(date_str, utc=True) < start_dt:
                continue
        except Exception:
            pass

        provider = content.get("provider", {})
        source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)
        if not source:
            source = item.get("publisher", "")

        url = content.get("canonicalUrl") or content.get("clickThroughUrl") or content.get("previewUrl") or item.get("link", "")

        results.append(CompanyNews(
            ticker=ticker,
            title=str(title),
            author=None,
            source=str(source),
            date=date_str,
            url=str(url),
            sentiment=None,
        ))

        if len(results) >= limit:
            break

    _cache.set_company_news(cache_key, [r.model_dump() for r in results])
    return results


# ---------------------------------------------------------------------------
# get_market_cap
# ---------------------------------------------------------------------------

def get_market_cap(ticker: str, end_date: str, api_key: str = None) -> float | None:
    """
    Fetch current market capitalisation via yfinance Ticker.info.
    """
    try:
        info = yf.Ticker(ticker).info
    except Exception as e:
        logger.warning("yfinance info failed for market_cap lookup %s: %s", ticker, e)
        return None
    return _none(info.get("marketCap"))


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

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
    """Convenience wrapper: fetch prices and return as DataFrame."""
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
