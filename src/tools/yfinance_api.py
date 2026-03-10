"""
yfinance adapter — provides the same interface as src/tools/api.py but uses
Yahoo Finance (yfinance) as the data source.  No API key required; works for
any publicly-listed ticker.
"""

import datetime
import logging

import pandas as pd
import yfinance as yf

from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> float | None:
    try:
        return float(val) if val is not None and str(val) != "nan" else None
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _fmt_date(ts) -> str:
    """Convert various timestamp types to YYYY-MM-DD string."""
    if isinstance(ts, str):
        return ts[:10]
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d")
    return str(ts)[:10]


# ---------------------------------------------------------------------------
# Module-level constants (built once, shared across all calls)
# ---------------------------------------------------------------------------

# Maps financialdatasets.ai line-item names → yfinance flat-dict key(s)
# (yfinance field names are lowercased with spaces/hyphens → underscores)
_FIELD_MAP: dict[str, list[str]] = {
    # Income statement
    "revenue": ["total_revenue", "operating_revenue"],
    "gross_profit": ["gross_profit"],
    "gross_margin": [],               # derived from info
    "operating_income": ["operating_income", "ebit"],
    "operating_margin": [],           # derived from info
    "operating_expense": ["operating_expense", "total_expenses"],
    "ebit": ["ebit"],
    "ebitda": ["ebitda", "normalized_ebitda"],
    "net_income": ["net_income", "net_income_common_stockholders"],
    "interest_expense": ["interest_expense", "interest_expense_non_operating"],
    "research_and_development": ["research_and_development"],
    "earnings_per_share": ["diluted_eps", "basic_eps", "trailingeps", "forwardeps"],
    # Cash flow
    "free_cash_flow": ["free_cash_flow"],
    "operating_cash_flow": ["operating_cash_flow"],
    "capital_expenditure": ["capital_expenditure"],
    "depreciation_and_amortization": [
        "depreciation_and_amortization",
        "depreciation_amortization_depletion",
        "reconciled_depreciation",
    ],
    "dividends_and_other_cash_distributions": ["common_stock_payments"],
    "issuance_or_purchase_of_equity_shares": [
        "net_common_stock_issuance",
        "common_stock_issuance",
        "repurchase_of_capital_stock",
    ],
    # Balance sheet
    "cash_and_equivalents": [
        "cash_and_cash_equivalents",
        "cash_cash_equivalents_and_short_term_investments",
    ],
    "total_assets": ["total_assets"],
    "total_liabilities": ["total_liabilities_net_minority_interest"],
    "total_debt": ["total_debt"],
    "shareholders_equity": ["stockholders_equity", "common_stock_equity"],
    "book_value_per_share": [],       # derived: equity / shares
    "current_assets": ["current_assets"],
    "current_liabilities": ["current_liabilities"],
    "working_capital": ["working_capital"],
    "goodwill_and_intangible_assets": ["goodwill_and_other_intangible_assets"],
    "intangible_assets": ["other_intangible_assets", "goodwill_and_other_intangible_assets"],
    "outstanding_shares": ["ordinary_shares_number", "share_issued", "diluted_average_shares"],
    "shares_outstanding": ["ordinary_shares_number", "share_issued"],
    "debt_to_equity": [],             # derived from info
    "return_on_invested_capital": [], # derived
}

# Maps line-item names to their .info camelCase key (None → return 0.0)
_INFO_KEY_MAP: dict[str, str | None] = {
    "earnings_per_share": "trailingEps",
    "dividends_and_other_cash_distributions": None,  # treat as 0 when absent
    "outstanding_shares": "sharesOutstanding",
    "shares_outstanding": "sharesOutstanding",
}


def _resolve_fields(
    requested_items: list[str],
    flat: dict[str, float | None],
    derived: dict[str, float | None],
    info: dict,
) -> dict[str, float | None]:
    """Resolve a list of requested line-item names against statement data and .info."""
    result: dict[str, float | None] = {}
    for requested in requested_items:
        key = requested.lower()
        # 1. Derived values (margins, ratios computed from info)
        if key in derived and derived[key] is not None:
            result[requested] = derived[key]
            continue
        # 2. Direct key match in flattened statements
        if key in flat:
            result[requested] = flat[key]
            continue
        # 3. FIELD_MAP aliases
        found: float | None = None
        for candidate in _FIELD_MAP.get(key, []):
            if candidate in flat:
                found = flat[candidate]
                break
        # 4. Fallback to .info (camelCase variants)
        if found is None:
            if key in _INFO_KEY_MAP:
                ik = _INFO_KEY_MAP[key]
                found = _safe_float(info.get(ik)) if ik else 0.0
            else:
                found = _safe_float(info.get(requested)) or _safe_float(info.get(key))
        result[requested] = found
    return result


def _debt_to_equity_from_info(info: dict) -> float | None:
    """Return D/E ratio from yfinance info (stored as %, convert to ratio)."""
    raw = _safe_float(info.get("debtToEquity"))
    return (raw / 100.0) if raw is not None else None


# ---------------------------------------------------------------------------
# Public API — mirrors src/tools/api.py signatures
# ---------------------------------------------------------------------------

def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch OHLCV prices from Yahoo Finance."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(start=start_date, end=end_date, auto_adjust=True)
        if df.empty:
            return []
        prices = []
        for ts, row in df.iterrows():
            prices.append(
                Price(
                    open=float(row["Open"]),
                    close=float(row["Close"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    volume=int(row["Volume"]),
                    time=_fmt_date(ts),
                )
            )
        return prices
    except Exception as exc:
        _log.warning("yfinance get_prices failed for %s: %s", ticker, exc)
        return []


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from Yahoo Finance info dict."""
    try:
        info = yf.Ticker(ticker).info
        if not info or (info.get("trailingPE") is None and info.get("marketCap") is None):
            return []

        market_cap = _safe_float(info.get("marketCap"))
        ev = _safe_float(info.get("enterpriseValue"))
        pe = _safe_float(info.get("trailingPE"))
        pb = _safe_float(info.get("priceToBook"))
        ps = _safe_float(info.get("priceToSalesTrailing12Months"))
        ev_ebitda = _safe_float(info.get("enterpriseToEbitda"))
        ev_rev = _safe_float(info.get("enterpriseToRevenue"))
        peg = _safe_float(info.get("pegRatio"))
        gross_margin = _safe_float(info.get("grossMargins"))
        op_margin = _safe_float(info.get("operatingMargins"))
        net_margin = _safe_float(info.get("profitMargins"))
        roe = _safe_float(info.get("returnOnEquity"))
        roa = _safe_float(info.get("returnOnAssets"))
        current_ratio = _safe_float(info.get("currentRatio"))
        quick_ratio = _safe_float(info.get("quickRatio"))
        # yfinance returns D/E as a percentage (e.g. 180 means 1.80); preserve 0.0 for debt-free cos
        debt_to_equity = _debt_to_equity_from_info(info)
        rev_growth = _safe_float(info.get("revenueGrowth"))
        earn_growth = _safe_float(info.get("earningsGrowth"))
        payout = _safe_float(info.get("payoutRatio"))
        eps = _safe_float(info.get("trailingEps"))
        book_per_share = _safe_float(info.get("bookValue"))
        fcf_per_share = _safe_float(info.get("freeCashflow"))
        if fcf_per_share is not None and _safe_float(info.get("sharesOutstanding")):
            fcf_per_share = fcf_per_share / info["sharesOutstanding"]

        report_period = end_date
        metrics = FinancialMetrics(
            ticker=ticker,
            report_period=report_period,
            period=period,
            currency=info.get("currency", "USD"),
            market_cap=market_cap,
            enterprise_value=ev,
            price_to_earnings_ratio=pe,
            price_to_book_ratio=pb,
            price_to_sales_ratio=ps,
            enterprise_value_to_ebitda_ratio=ev_ebitda,
            enterprise_value_to_revenue_ratio=ev_rev,
            free_cash_flow_yield=None,
            peg_ratio=peg,
            gross_margin=gross_margin,
            operating_margin=op_margin,
            net_margin=net_margin,
            return_on_equity=roe,
            return_on_assets=roa,
            return_on_invested_capital=None,
            asset_turnover=None,
            inventory_turnover=None,
            receivables_turnover=None,
            days_sales_outstanding=None,
            operating_cycle=None,
            working_capital_turnover=None,
            current_ratio=current_ratio,
            quick_ratio=quick_ratio,
            cash_ratio=None,
            operating_cash_flow_ratio=None,
            debt_to_equity=debt_to_equity,
            debt_to_assets=None,
            interest_coverage=None,
            revenue_growth=rev_growth,
            earnings_growth=earn_growth,
            book_value_growth=None,
            earnings_per_share_growth=None,
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=payout,
            earnings_per_share=eps,
            book_value_per_share=book_per_share,
            free_cash_flow_per_share=fcf_per_share,
        )
        return [metrics]
    except Exception as exc:
        _log.warning("yfinance get_financial_metrics failed for %s: %s", ticker, exc)
        return []


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    """
    Map requested line-item names to yfinance financial statements.
    Supports income_statement, balance_sheet, and cash_flow fields.
    """
    try:
        t = yf.Ticker(ticker)
        # Fetch all three statement types
        if period in ("ttm", "annual"):
            stmts = [t.financials, t.balance_sheet, t.cashflow]
        else:
            stmts = [t.quarterly_financials, t.quarterly_balance_sheet, t.quarterly_cashflow]

        info = t.info or {}
        shares_out = _safe_float(info.get("sharesOutstanding"))

        def _build_flat(col_selector) -> dict[str, float | None]:
            """Flatten all statement rows for a given column-selector callable."""
            flat: dict[str, float | None] = {}
            for stmt in stmts:
                if stmt is None or stmt.empty:
                    continue
                col = col_selector(stmt)
                for idx in stmt.index:
                    k = str(idx).lower().replace(" ", "_").replace("-", "_")
                    v = _safe_float(stmt.loc[idx, col])
                    if v is not None:
                        flat[k] = v
            return flat

        def _build_derived(flat: dict[str, float | None]) -> dict[str, float | None]:
            equity = flat.get("stockholders_equity") or flat.get("common_stock_equity")
            return {
                "gross_margin": _safe_float(info.get("grossMargins")),
                "operating_margin": _safe_float(info.get("operatingMargins")),
                "debt_to_equity": _debt_to_equity_from_info(info),
                "return_on_invested_capital": _safe_float(info.get("returnOnEquity")),
                "book_value_per_share": (
                    equity / shares_out
                    if equity and shares_out
                    else _safe_float(info.get("bookValue"))
                ),
            }

        # Determine available periods from the first non-empty statement
        periods_available: list[str] = []
        for stmt in stmts:
            if stmt is not None and not stmt.empty:
                periods_available = [
                    _fmt_date(col) for col in stmt.columns if _fmt_date(col) <= end_date
                ]
                break

        if not periods_available:
            # Fallback: single record using most-recent column data
            flat = _build_flat(lambda s: s.columns[0])
            result = _resolve_fields(line_items, flat, _build_derived(flat), info)
            return [LineItem(
                ticker=ticker,
                report_period=end_date,
                period=period,
                currency=info.get("currency", "USD"),
                **result,
            )]

        # Build one LineItem per available period (up to limit)
        line_items_out = []
        for period_date in periods_available[:limit]:
            def _select_col(stmt, pd=period_date):
                matching = [c for c in stmt.columns if _fmt_date(c) == pd]
                return matching[0] if matching else stmt.columns[0]

            period_flat = _build_flat(_select_col)
            period_result = _resolve_fields(line_items, period_flat, _build_derived(period_flat), info)
            line_items_out.append(LineItem(
                ticker=ticker,
                report_period=period_date,
                period=period,
                currency=info.get("currency", "USD"),
                **period_result,
            ))

        return line_items_out
    except Exception as exc:
        _log.warning("yfinance search_line_items failed for %s: %s", ticker, exc)
        return []


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[InsiderTrade]:
    """Fetch insider trades from Yahoo Finance."""
    try:
        df = yf.Ticker(ticker).insider_transactions
        if df is None or df.empty:
            return []

        trades = []
        for _, row in df.iterrows():
            filing_date = _fmt_date(row.get("startDate") or row.get("Start Date") or end_date)

            # Date filtering
            if start_date and filing_date < start_date:
                continue
            if filing_date > end_date:
                continue

            shares = _safe_float(row.get("shares") or row.get("Shares"))
            value = _safe_float(row.get("value") or row.get("Value"))
            text = str(row.get("text") or row.get("Text") or "")

            trade = InsiderTrade(
                ticker=ticker,
                issuer=ticker,
                name=str(row.get("filerName") or row.get("Filer Name") or ""),
                title=str(row.get("filerRelation") or row.get("Filer Relation") or ""),
                is_board_director=None,
                transaction_date=filing_date,
                transaction_shares=shares,
                transaction_price_per_share=None,
                transaction_value=value,
                shares_owned_before_transaction=None,
                shares_owned_after_transaction=None,
                security_title="Common Stock",
                filing_date=filing_date,
            )
            trades.append(trade)
            if len(trades) >= limit:
                break

        return trades
    except Exception as exc:
        _log.warning("yfinance get_insider_trades failed for %s: %s", ticker, exc)
        return []


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[CompanyNews]:
    """Fetch company news from Yahoo Finance."""
    try:
        news_list = yf.Ticker(ticker).news
        if not news_list:
            return []

        results = []
        for item in news_list:
            # providerPublishTime is a Unix timestamp
            pub_ts = item.get("providerPublishTime")
            if pub_ts:
                date_str = datetime.datetime.fromtimestamp(pub_ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            else:
                date_str = end_date

            if start_date and date_str < start_date:
                continue
            if date_str > end_date:
                continue

            # Handle nested content structure in newer yfinance versions
            content = item.get("content", item)
            title = content.get("title") or item.get("title") or ""
            url = ""
            if "canonicalUrl" in content:
                url = content["canonicalUrl"].get("url", "")
            elif "clickThroughUrl" in content:
                url = content["clickThroughUrl"].get("url", "")
            else:
                url = item.get("link") or ""

            provider = content.get("provider", {})
            source = provider.get("displayName") if isinstance(provider, dict) else str(provider)
            source = source or item.get("publisher") or "Yahoo Finance"

            results.append(
                CompanyNews(
                    ticker=ticker,
                    title=title,
                    author="",
                    source=source,
                    date=date_str,
                    url=url,
                    sentiment=None,
                )
            )
            if len(results) >= limit:
                break

        return results
    except Exception as exc:
        _log.warning("yfinance get_company_news failed for %s: %s", ticker, exc)
        return []


def get_market_cap(ticker: str, end_date: str) -> float | None:
    """Fetch current market cap from Yahoo Finance."""
    try:
        info = yf.Ticker(ticker).info
        return _safe_float(info.get("marketCap"))
    except Exception as exc:
        _log.warning("yfinance get_market_cap failed for %s: %s", ticker, exc)
        return None


def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Return prices as a DataFrame (mirrors api.prices_to_df output format)."""
    prices = get_prices(ticker, start_date, end_date)
    if not prices:
        return pd.DataFrame()
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    for col in ["open", "close", "high", "low", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df
