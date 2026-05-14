"""Financial data layer — backed by yfinance (free, no API key required).

Replacements vs. original Financial Datasets API:
  - Prices, metrics, line items, news, market cap → yfinance
  - Insider trades → SEC EDGAR Form 4 filings (free, no key)
  - News sentiment → always None (yfinance doesn't score sentiment)
  - peg_ratio / operating_cycle → always None (not in yfinance statements)
"""

from __future__ import annotations

import datetime
import logging
import math
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    Price,
    LineItem,
    InsiderTrade,
)

_cache = get_cache()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe(val) -> float | None:
    """Return float or None, squashing NaN/Inf."""
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _div(a, b) -> float | None:
    """Safe division; returns None when b is zero or either operand is None."""
    if a is None or b is None or b == 0:
        return None
    return _safe(a / b)


def _growth(current, previous) -> float | None:
    """Period-over-period growth: (curr - prev) / abs(prev)."""
    if current is None or previous is None or previous == 0:
        return None
    return _safe((current - previous) / abs(previous))


def _stmt_val(df: pd.DataFrame, col, *row_names: str) -> float | None:
    """Return the first matching row value from a statement DataFrame column."""
    if df is None or df.empty or col is None or col not in df.columns:
        return None
    for row in row_names:
        try:
            if row in df.index:
                v = df.loc[row, col]
                if v is not None and pd.notna(v):
                    return float(v)
        except Exception:
            continue
    return None


def _nearest_col(df: pd.DataFrame, target):
    """Return the column in df whose date is nearest to target (within 45 days)."""
    if df is None or df.empty or target is None:
        return None
    if target in df.columns:
        return target
    target_ts = pd.Timestamp(target)
    diffs = {c: abs((pd.Timestamp(c) - target_ts).days) for c in df.columns}
    nearest = min(diffs, key=diffs.get)
    return nearest if diffs[nearest] <= 45 else None


def _model_to_dict(obj) -> dict:
    """Pydantic v1/v2 compatible serialisation."""
    return obj.dict() if hasattr(obj, "dict") else obj.model_dump()


# ---------------------------------------------------------------------------
# Mappings: logical line-item names → yfinance DataFrame row names
# ---------------------------------------------------------------------------

_INC_ROWS: dict[str, list[str]] = {
    "revenue": ["Total Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "EBIT"],
    "ebit": ["EBIT", "Operating Income"],
    "net_income": ["Net Income"],
    "earnings_per_share": ["Basic EPS", "Diluted EPS"],
    "interest_expense": ["Interest Expense"],
    "depreciation_and_amortization": ["Reconciled Depreciation"],
    "research_and_development": ["Research And Development"],
}

_BAL_ROWS: dict[str, list[str]] = {
    "total_assets": ["Total Assets"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "total_liabilities": ["Total Liabilities Net Minority Interest"],
    "shareholders_equity": ["Stockholders Equity", "Common Stock Equity"],
    "total_debt": ["Total Debt"],
    "cash_and_equivalents": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "outstanding_shares": ["Share Issued", "Ordinary Shares Number"],
}

_CF_ROWS: dict[str, list[str]] = {
    "free_cash_flow": ["Free Cash Flow"],
    "capital_expenditure": ["Capital Expenditure"],
    "dividends_and_other_cash_distributions": ["Common Stock Dividend Paid", "Cash Dividends Paid"],
    "issuance_or_purchase_of_equity_shares": ["Repurchase Of Capital Stock", "Issuance Of Capital Stock"],
}


# ---------------------------------------------------------------------------
# get_prices
# ---------------------------------------------------------------------------

def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Fetch daily OHLCV bars from yfinance."""
    cache_key = f"{ticker}_{start_date}_{end_date}"
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**p) for p in cached_data]

    try:
        hist = yf.Ticker(ticker).history(start=start_date, end=end_date, interval="1d", auto_adjust=True)
    except Exception as e:
        logger.warning("yfinance price fetch failed for %s: %s", ticker, e)
        return []

    if hist is None or hist.empty:
        return []

    prices = [
        Price(
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
            time=dt.isoformat(),
        )
        for dt, row in hist.iterrows()
    ]
    _cache.set_prices(cache_key, [_model_to_dict(p) for p in prices])
    return prices


# ---------------------------------------------------------------------------
# Financial metrics helpers
# ---------------------------------------------------------------------------

def _metrics_dict_from_statements(
    ticker: str,
    inc_col,
    period_label: str,
    inc: pd.DataFrame,
    bal: pd.DataFrame,
    cf: pd.DataFrame,
    price: float | None,
) -> dict:
    """Compute one FinancialMetrics record as a plain dict (no model mutation needed)."""
    report_period = inc_col.strftime("%Y-%m-%d") if hasattr(inc_col, "strftime") else str(inc_col)[:10]

    bal_col = _nearest_col(bal, inc_col)
    cf_col  = _nearest_col(cf,  inc_col)

    # Income statement
    revenue          = _stmt_val(inc, inc_col, "Total Revenue")
    gross_profit     = _stmt_val(inc, inc_col, "Gross Profit")
    operating_income = _stmt_val(inc, inc_col, "Operating Income", "EBIT")
    net_income       = _stmt_val(inc, inc_col, "Net Income")
    ebitda           = _stmt_val(inc, inc_col, "EBITDA")
    interest_expense = _stmt_val(inc, inc_col, "Interest Expense")
    eps              = _stmt_val(inc, inc_col, "Basic EPS", "Diluted EPS")

    # Balance sheet
    total_assets   = _stmt_val(bal, bal_col, "Total Assets")
    current_assets = _stmt_val(bal, bal_col, "Current Assets")
    current_liab   = _stmt_val(bal, bal_col, "Current Liabilities")
    total_debt     = _stmt_val(bal, bal_col, "Total Debt")
    equity         = _stmt_val(bal, bal_col, "Stockholders Equity", "Common Stock Equity")
    cash           = _stmt_val(bal, bal_col, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
    inventory      = _stmt_val(bal, bal_col, "Inventory")
    receivables    = _stmt_val(bal, bal_col, "Accounts Receivable")
    shares         = _stmt_val(bal, bal_col, "Share Issued", "Ordinary Shares Number")

    # Cash flow
    operating_cf = _stmt_val(cf, cf_col, "Operating Cash Flow")
    capex        = _stmt_val(cf, cf_col, "Capital Expenditure")
    # capex is negative in yfinance; FCF = OCF + capex
    free_cash_flow = (operating_cf + capex) if (operating_cf is not None and capex is not None) else _stmt_val(cf, cf_col, "Free Cash Flow")

    # Market cap and EV
    market_cap = (price * shares) if (price is not None and shares is not None) else None
    net_debt   = (total_debt or 0) - (cash or 0) if total_debt is not None else None
    ev         = (market_cap + net_debt) if (market_cap is not None and net_debt is not None) else None

    wc       = (current_assets - current_liab) if (current_assets is not None and current_liab is not None) else None
    ic       = (total_debt + equity) if (total_debt is not None and equity is not None) else None
    quick_num = (current_assets - inventory) if (current_assets is not None and inventory is not None) else current_assets
    # interest_expense is negative in yfinance; negate for coverage ratio
    ie       = -interest_expense if (interest_expense is not None and interest_expense < 0) else interest_expense

    return dict(
        ticker=ticker,
        report_period=report_period,
        period=period_label,
        currency="USD",
        market_cap=market_cap,
        enterprise_value=ev,
        price_to_earnings_ratio=_div(market_cap, net_income),
        price_to_book_ratio=_div(market_cap, equity),
        price_to_sales_ratio=_div(market_cap, revenue),
        enterprise_value_to_ebitda_ratio=_div(ev, ebitda),
        enterprise_value_to_revenue_ratio=_div(ev, revenue),
        free_cash_flow_yield=_div(free_cash_flow, market_cap),
        peg_ratio=None,
        gross_margin=_div(gross_profit, revenue),
        operating_margin=_div(operating_income, revenue),
        net_margin=_div(net_income, revenue),
        return_on_equity=_div(net_income, equity),
        return_on_assets=_div(net_income, total_assets),
        return_on_invested_capital=_div(operating_income, ic),
        asset_turnover=_div(revenue, total_assets),
        inventory_turnover=_div(revenue, inventory),
        receivables_turnover=_div(revenue, receivables),
        days_sales_outstanding=_div(365.0, _div(revenue, receivables)),
        operating_cycle=None,
        working_capital_turnover=_div(revenue, wc),
        current_ratio=_div(current_assets, current_liab),
        quick_ratio=_div(quick_num, current_liab),
        cash_ratio=_div(cash, current_liab),
        operating_cash_flow_ratio=_div(operating_cf, current_liab),
        debt_to_equity=_div(total_debt, equity),
        debt_to_assets=_div(total_debt, total_assets),
        interest_coverage=_div(operating_income, ie),
        revenue_growth=None,
        earnings_growth=None,
        book_value_growth=None,
        earnings_per_share_growth=None,
        free_cash_flow_growth=None,
        operating_income_growth=None,
        ebitda_growth=None,
        payout_ratio=None,
        earnings_per_share=eps,
        book_value_per_share=_div(equity, shares),
        free_cash_flow_per_share=_div(free_cash_flow, shares),
    )


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
    """Fetch financial metrics from yfinance.

    For period='ttm' returns a single current snapshot from Ticker.info.
    For period='annual' or 'quarterly' computes ratios from statement DataFrames.
    Note: peg_ratio and operating_cycle are always None (not in yfinance).
    """
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**m) for m in cached_data]

    try:
        yf_ticker = yf.Ticker(ticker)
    except Exception as e:
        logger.warning("yfinance init failed for %s: %s", ticker, e)
        return []

    end_dt = datetime.date.fromisoformat(end_date)

    # --- TTM: use .info snapshot (always current, not point-in-time) ---
    if period == "ttm":
        try:
            info = yf_ticker.info
        except Exception as e:
            logger.warning("yfinance .info failed for %s: %s", ticker, e)
            return []

        shares     = _safe(info.get("sharesOutstanding"))
        market_cap = _safe(info.get("marketCap"))
        fcf        = _safe(info.get("freeCashflow"))
        # yfinance returns debtToEquity as a percentage (150 = 1.5x); normalise to ratio
        raw_de     = _safe(info.get("debtToEquity"))

        m = FinancialMetrics(
            ticker=ticker,
            report_period=end_date,
            period="ttm",
            currency=info.get("currency", "USD"),
            market_cap=market_cap,
            enterprise_value=_safe(info.get("enterpriseValue")),
            price_to_earnings_ratio=_safe(info.get("trailingPE")),
            price_to_book_ratio=_safe(info.get("priceToBook")),
            price_to_sales_ratio=_safe(info.get("priceToSalesTrailing12Months")),
            enterprise_value_to_ebitda_ratio=_safe(info.get("enterpriseToEbitda")),
            enterprise_value_to_revenue_ratio=_safe(info.get("enterpriseToRevenue")),
            free_cash_flow_yield=_div(fcf, market_cap),
            peg_ratio=_safe(info.get("pegRatio")),
            gross_margin=_safe(info.get("grossMargins")),
            operating_margin=_safe(info.get("operatingMargins")),
            net_margin=_safe(info.get("profitMargins")),
            return_on_equity=_safe(info.get("returnOnEquity")),
            return_on_assets=_safe(info.get("returnOnAssets")),
            return_on_invested_capital=None,
            asset_turnover=None,
            inventory_turnover=None,
            receivables_turnover=None,
            days_sales_outstanding=None,
            operating_cycle=None,
            working_capital_turnover=None,
            current_ratio=_safe(info.get("currentRatio")),
            quick_ratio=_safe(info.get("quickRatio")),
            cash_ratio=None,
            operating_cash_flow_ratio=None,
            debt_to_equity=_div(raw_de, 100.0) if raw_de is not None else None,
            debt_to_assets=None,
            interest_coverage=None,
            revenue_growth=_safe(info.get("revenueGrowth")),
            earnings_growth=_safe(info.get("earningsGrowth")),
            book_value_growth=None,
            earnings_per_share_growth=None,
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=_safe(info.get("payoutRatio")),
            earnings_per_share=_safe(info.get("trailingEps")),
            book_value_per_share=_safe(info.get("bookValue")),
            free_cash_flow_per_share=_div(fcf, shares),
        )
        metrics = [m]
        _cache.set_financial_metrics(cache_key, [_model_to_dict(x) for x in metrics])
        return metrics

    # --- Historical: compute from statement DataFrames ---
    try:
        if period == "quarterly":
            inc = yf_ticker.quarterly_income_stmt
            bal = yf_ticker.quarterly_balance_sheet
            cf  = yf_ticker.quarterly_cash_flow
            period_label = "quarterly"
        else:
            inc = yf_ticker.income_stmt
            bal = yf_ticker.balance_sheet
            cf  = yf_ticker.cash_flow
            period_label = "annual"
    except Exception as e:
        logger.warning("yfinance statements failed for %s: %s", ticker, e)
        return []

    if inc is None or inc.empty:
        return []

    # Fetch price history to compute market-cap-based ratios
    price_history = get_prices(ticker, "2010-01-01", end_date)
    price_df = prices_to_df(price_history) if price_history else pd.DataFrame()

    def _price_near(dt) -> float | None:
        if price_df.empty:
            return None
        try:
            idx = price_df.index.get_indexer([pd.Timestamp(dt)], method="nearest")[0]
            return float(price_df.iloc[idx]["close"])
        except Exception:
            return None

    cols     = sorted(inc.columns, reverse=True)
    in_range = [c for c in cols if c.date() <= end_dt]
    extra    = cols[len(in_range)] if len(in_range) < len(cols) else None

    metrics: list[FinancialMetrics] = []
    for i, col in enumerate(in_range[:limit]):
        prev_col = in_range[i + 1] if i + 1 < len(in_range) else extra

        d = _metrics_dict_from_statements(ticker, col, period_label, inc, bal, cf, _price_near(col.date()))

        if prev_col is not None:
            d["revenue_growth"]           = _growth(_stmt_val(inc, col, "Total Revenue"),              _stmt_val(inc, prev_col, "Total Revenue"))
            d["earnings_growth"]          = _growth(_stmt_val(inc, col, "Net Income"),                 _stmt_val(inc, prev_col, "Net Income"))
            d["operating_income_growth"]  = _growth(_stmt_val(inc, col, "Operating Income", "EBIT"),   _stmt_val(inc, prev_col, "Operating Income", "EBIT"))
            d["ebitda_growth"]            = _growth(_stmt_val(inc, col, "EBITDA"),                     _stmt_val(inc, prev_col, "EBITDA"))
            d["earnings_per_share_growth"]= _growth(_stmt_val(inc, col, "Basic EPS", "Diluted EPS"),   _stmt_val(inc, prev_col, "Basic EPS", "Diluted EPS"))
            d["book_value_growth"]        = _growth(
                _stmt_val(bal, _nearest_col(bal, col),      "Stockholders Equity", "Common Stock Equity"),
                _stmt_val(bal, _nearest_col(bal, prev_col), "Stockholders Equity", "Common Stock Equity"),
            )
            cf_c = _nearest_col(cf, col);      cf_p = _nearest_col(cf, prev_col)
            ocf_c = _stmt_val(cf, cf_c, "Operating Cash Flow"); cap_c = _stmt_val(cf, cf_c, "Capital Expenditure")
            ocf_p = _stmt_val(cf, cf_p, "Operating Cash Flow"); cap_p = _stmt_val(cf, cf_p, "Capital Expenditure")
            fcf_c = (ocf_c + cap_c) if (ocf_c and cap_c) else _stmt_val(cf, cf_c, "Free Cash Flow")
            fcf_p = (ocf_p + cap_p) if (ocf_p and cap_p) else _stmt_val(cf, cf_p, "Free Cash Flow")
            d["free_cash_flow_growth"]    = _growth(fcf_c, fcf_p)

        metrics.append(FinancialMetrics(**d))

    if not metrics:
        return []
    _cache.set_financial_metrics(cache_key, [_model_to_dict(m) for m in metrics])
    return metrics


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
    """Fetch financial line items from yfinance statement DataFrames.

    Computed items (gross_margin, operating_margin, debt_to_equity,
    return_on_invested_capital, working_capital, book_value_per_share)
    are derived on the fly from raw statement values.
    """
    try:
        yf_ticker = yf.Ticker(ticker)
    except Exception as e:
        logger.warning("yfinance init failed for %s: %s", ticker, e)
        return []

    end_dt = datetime.date.fromisoformat(end_date)

    try:
        if period == "quarterly":
            inc = yf_ticker.quarterly_income_stmt
            bal = yf_ticker.quarterly_balance_sheet
            cf  = yf_ticker.quarterly_cash_flow
            period_label = "quarterly"
        else:
            inc = yf_ticker.income_stmt
            bal = yf_ticker.balance_sheet
            cf  = yf_ticker.cash_flow
            period_label = "annual" if period == "annual" else "ttm"
    except Exception as e:
        logger.warning("yfinance statements failed for %s: %s", ticker, e)
        return []

    if inc is None or inc.empty:
        return []

    cols = [c for c in sorted(inc.columns, reverse=True) if c.date() <= end_dt]

    results: list[LineItem] = []
    for col in cols[:limit]:
        bal_col = _nearest_col(bal, col)
        cf_col  = _nearest_col(cf, col)
        report_period = col.strftime("%Y-%m-%d")

        fields: dict[str, float | None] = {}
        for name in line_items:
            val: float | None = None
            if name in _INC_ROWS:
                val = _stmt_val(inc, col, *_INC_ROWS[name])
            elif name in _BAL_ROWS:
                val = _stmt_val(bal, bal_col, *_BAL_ROWS[name])
            elif name in _CF_ROWS:
                val = _stmt_val(cf, cf_col, *_CF_ROWS[name])
            elif name == "gross_margin":
                val = _div(_stmt_val(inc, col, "Gross Profit"), _stmt_val(inc, col, "Total Revenue"))
            elif name == "operating_margin":
                val = _div(_stmt_val(inc, col, "Operating Income", "EBIT"), _stmt_val(inc, col, "Total Revenue"))
            elif name == "debt_to_equity":
                val = _div(_stmt_val(bal, bal_col, "Total Debt"), _stmt_val(bal, bal_col, "Stockholders Equity", "Common Stock Equity"))
            elif name == "return_on_invested_capital":
                oi   = _stmt_val(inc, col, "Operating Income", "EBIT")
                debt = _stmt_val(bal, bal_col, "Total Debt")
                eq   = _stmt_val(bal, bal_col, "Stockholders Equity", "Common Stock Equity")
                ic   = (debt + eq) if (debt is not None and eq is not None) else None
                val  = _div(oi, ic)
            elif name == "working_capital":
                ca = _stmt_val(bal, bal_col, "Current Assets")
                cl = _stmt_val(bal, bal_col, "Current Liabilities")
                val = (ca - cl) if (ca is not None and cl is not None) else None
            elif name == "book_value_per_share":
                eq     = _stmt_val(bal, bal_col, "Stockholders Equity", "Common Stock Equity")
                shares = _stmt_val(bal, bal_col, "Share Issued", "Ordinary Shares Number")
                val    = _div(eq, shares)
            fields[name] = val

        results.append(LineItem(
            ticker=ticker,
            report_period=report_period,
            period=period_label,
            currency="USD",
            **fields,
        ))

    return results[:limit]


# ---------------------------------------------------------------------------
# Insider trades — SEC EDGAR Form 4
# ---------------------------------------------------------------------------

_CIK_CACHE: dict[str, str] = {}
_EDGAR_HEADERS = {"User-Agent": "ai-hedge-fund research@example.com"}


def _get_cik(ticker: str) -> str | None:
    """Resolve ticker to a 10-digit SEC CIK using EDGAR's company_tickers.json."""
    if ticker in _CIK_CACHE:
        return _CIK_CACHE[ticker]
    try:
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=_EDGAR_HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        upper = ticker.upper()
        for entry in resp.json().values():
            if entry.get("ticker", "").upper() == upper:
                cik = str(entry["cik_str"]).zfill(10)
                _CIK_CACHE[ticker] = cik
                return cik
    except Exception as e:
        logger.warning("CIK lookup failed for %s: %s", ticker, e)
    return None


def _parse_form4_xml(content: bytes, ticker: str, filing_date: str) -> list[InsiderTrade]:
    """Parse a Form 4 XML document into InsiderTrade records."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    def _text(*tags: str) -> str | None:
        for tag in tags:
            node = root.find(f".//{tag}")
            if node is not None and node.text:
                return node.text.strip()
        return None

    name     = _text("rptOwnerName")
    issuer   = _text("issuerName")
    title    = _text("officerTitle")
    is_board = _text("isDirector") == "1"

    trades: list[InsiderTrade] = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        def _tx(tag: str) -> str | None:
            node = tx.find(f".//{tag}")
            return node.text.strip() if node is not None and node.text else None

        security_title   = _tx("securityTitle")
        transaction_date = _tx("transactionDate")
        acquired_code    = _tx("transactionAcquiredDisposedCode")

        try:
            raw_shares = _tx("transactionShares")
            shares = float(raw_shares) if raw_shares else None
            if shares and acquired_code == "D":
                shares = -shares
        except (TypeError, ValueError):
            shares = None

        try:
            raw_price = _tx("transactionPricePerShare")
            price = float(raw_price) if raw_price else None
        except (TypeError, ValueError):
            price = None

        try:
            raw_after = _tx("sharesOwnedFollowingTransaction")
            shares_after = float(raw_after) if raw_after else None
        except (TypeError, ValueError):
            shares_after = None

        value = (abs(shares) * price) if (shares and price) else None
        if acquired_code == "D" and value:
            value = -value

        trades.append(InsiderTrade(
            ticker=ticker,
            issuer=issuer,
            name=name,
            title=title,
            is_board_director=is_board,
            transaction_date=transaction_date,
            transaction_shares=shares,
            transaction_price_per_share=price,
            transaction_value=value,
            shares_owned_before_transaction=None,
            shares_owned_after_transaction=shares_after,
            security_title=security_title,
            filing_date=filing_date,
        ))
    return trades


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from SEC EDGAR Form 4 filings (free, no API key)."""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**t) for t in cached_data]

    cik = _get_cik(ticker)
    if not cik:
        logger.warning("No CIK found for %s; returning empty insider trades", ticker)
        return []

    try:
        resp = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=_EDGAR_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        recent = resp.json().get("filings", {}).get("recent", {})
    except Exception as e:
        logger.warning("EDGAR submissions fetch failed for %s: %s", ticker, e)
        return []

    form_types   = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accessions   = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    all_trades: list[InsiderTrade] = []
    for i, form_type in enumerate(form_types):
        if len(all_trades) >= limit:
            break
        if form_type not in ("4", "4/A"):
            continue
        fd = filing_dates[i]
        if fd > end_date:
            continue
        if start_date and fd < start_date:
            continue

        acc_nodash  = accessions[i].replace("-", "")
        primary_doc = primary_docs[i] if i < len(primary_docs) else "form4.xml"
        xml_url     = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{primary_doc}"

        try:
            xml_resp = requests.get(xml_url, headers=_EDGAR_HEADERS, timeout=10)
            if xml_resp.status_code != 200:
                continue
        except Exception:
            continue

        all_trades.extend(_parse_form4_xml(xml_resp.content, ticker, fd))
        time.sleep(0.15)  # respect EDGAR's rate limit

    all_trades = all_trades[:limit]
    if all_trades:
        _cache.set_insider_trades(cache_key, [_model_to_dict(t) for t in all_trades])
    return all_trades


# ---------------------------------------------------------------------------
# Company news — yfinance
# ---------------------------------------------------------------------------

def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news from yfinance.

    Note: sentiment is always None — yfinance does not score sentiment.
    For scored sentiment consider running FinBERT on the returned titles.
    """
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**n) for n in cached_data]

    try:
        raw_news = yf.Ticker(ticker).news
    except Exception as e:
        logger.warning("yfinance news fetch failed for %s: %s", ticker, e)
        return []

    if not raw_news:
        return []

    articles: list[CompanyNews] = []
    for item in raw_news:
        pub_ts = item.get("providerPublishTime")
        if not pub_ts:
            continue
        dt = datetime.datetime.fromtimestamp(pub_ts, tz=datetime.timezone.utc)
        date_only = dt.date().isoformat()
        if date_only > end_date:
            continue
        if start_date and date_only < start_date:
            continue
        articles.append(CompanyNews(
            ticker=ticker,
            title=item.get("title", ""),
            author=None,
            source=item.get("publisher", ""),
            date=dt.isoformat(),
            url=item.get("link", ""),
            sentiment=None,
        ))

    articles = articles[:limit]
    if articles:
        _cache.set_company_news(cache_key, [_model_to_dict(n) for n in articles])
    return articles


# ---------------------------------------------------------------------------
# Market cap
# ---------------------------------------------------------------------------

def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap via yfinance."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    if end_date >= today:
        try:
            if mc := _safe(yf.Ticker(ticker).info.get("marketCap")):
                return mc
        except Exception:
            pass

    # Historical: delegate to financial metrics (TTM snapshot)
    metrics = get_financial_metrics(ticker, end_date, period="ttm", api_key=api_key)
    if metrics and metrics[0].market_cap is not None:
        return metrics[0].market_cap

    # Last resort: price × shares outstanding
    try:
        info   = yf.Ticker(ticker).info
        shares = _safe(info.get("sharesOutstanding"))
        if shares:
            prev   = (datetime.date.fromisoformat(end_date) - datetime.timedelta(days=5)).isoformat()
            prices = get_prices(ticker, prev, end_date)
            if prices:
                return prices[-1].close * shares
    except Exception as e:
        logger.warning("Market cap fallback failed for %s: %s", ticker, e)
    return None


# ---------------------------------------------------------------------------
# DataFrame utilities (unchanged interface)
# ---------------------------------------------------------------------------

def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert a list of Price objects to a DataFrame indexed by Date."""
    df = pd.DataFrame([_model_to_dict(p) for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    for col in ["open", "close", "high", "low", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    return prices_to_df(get_prices(ticker, start_date, end_date, api_key=api_key))
