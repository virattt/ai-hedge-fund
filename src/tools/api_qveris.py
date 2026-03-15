"""Qveris provider for financial data.

Uses the Qveris capability-discovery platform (https://qveris.ai) to find and
call third-party financial APIs at runtime.  No specific data provider is
hard-coded — Qveris selects the best available tool for each capability.

Required environment variable:
    QVERIS_API_KEY   — get yours at https://qveris.ai

Flow for every public function:
  1. _discover_tool(query) — POST /search → find the best tool for a
     capability description.  Discovery results are cached in-memory for the
     duration of the process so each query is resolved only once per run.
  2. _call_tool(tool_id, search_id, parameters) — POST /tools/execute →
     execute the tool and return the raw JSON result.
  3. A _parse_*() helper maps the variable JSON response to our Pydantic
     models using multiple field-name aliases (Alpha Vantage, Polygon, IEX,
     Finnhub, Yahoo-style, etc.).

Limitations:
  - The exact data available depends on which tool Qveris discovers; some
    fields may be None if the underlying provider does not supply them.
  - search_line_items attempts camelCase and snake_case conversions but may
    miss fields with non-standard naming.
  - Tool discovery adds ~1–3 s of latency the first time each data type is
    requested within a session (subsequent calls use the cached tool ID).
"""

import datetime
import logging
import math
import os

import pandas as pd
import requests

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

_QVERIS_BASE_URL = "https://qveris.ai/api/v1"

# In-process discovery cache: query string → {search_id, tool_id}
_discovery_cache: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Qveris HTTP client
# ---------------------------------------------------------------------------
def _get_api_key() -> str:
    key = os.environ.get("QVERIS_API_KEY", "")
    if not key:
        raise ValueError("QVERIS_API_KEY environment variable is not set. Get a key at https://qveris.ai")
    return key


def _qveris_post(path: str, body: dict, query_params: dict | None = None, timeout: int = 30) -> dict:
    url = f"{_QVERIS_BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=body, params=query_params, timeout=timeout)
    if not response.ok:
        raise RuntimeError(f"Qveris API {response.status_code}: {response.text[:400]}")
    return response.json()


def _discover_tools(query: str, limit: int = 8) -> dict | None:
    """Return {search_id, tools: [tool_id, ...]} for all tools matching *query*,
    sorted by success_rate descending.  Results are cached per process.
    """
    if query in _discovery_cache:
        return _discovery_cache[query]

    try:
        data = _qveris_post("/search", {"query": query, "limit": limit})
        results = data.get("results") or []
        if not results:
            logger.warning("Qveris: no tools found for query: %s", query)
            return None
        sorted_results = sorted(results, key=lambda r: (r.get("stats") or {}).get("success_rate", 0), reverse=True)
        entry = {
            "search_id": data.get("search_id"),
            "tools": [r["tool_id"] for r in sorted_results],
            # Keep backward-compat key pointing to the best tool
            "tool_id": sorted_results[0]["tool_id"],
        }
        _discovery_cache[query] = entry
        logger.debug("Qveris: discovered %d tools for query: %s", len(entry["tools"]), query)
        return entry
    except Exception as e:
        logger.warning("Qveris: discovery failed for '%s': %s", query, e)
        return None


def _discover_tool(query: str, limit: int = 8) -> dict | None:
    """Backward-compatible wrapper — returns the best single tool entry."""
    return _discover_tools(query, limit)


_API_ERROR_KEYS = frozenset({"Information", "Note", "error", "Error", "message", "fault"})


def _looks_like_error(result: dict) -> bool:
    """Return True if result is an API error/rate-limit envelope (no real data)."""
    if not result:
        return True
    # All keys are error-indicator keys (e.g. {"Information": "rate limit..."})
    if all(k in _API_ERROR_KEYS for k in result):
        return True
    # Has an explicit error/status field indicating failure
    status = result.get("status") or result.get("Status") or ""
    if isinstance(status, str) and status.lower() in ("error", "fail", "failed"):
        return True
    return False


def _call_tool_any(query: str, parameters: dict, max_response_size: int = 102400, timeout: int = 60) -> dict | None:
    """Discover tools for *query* and try each in success-rate order until one
    returns a non-empty, non-error result.  This handles cases where the top-ranked
    tool lacks coverage for the requested ticker (e.g. newer IPOs) or rate-limits."""
    discovery = _discover_tools(query)
    if not discovery:
        return None
    search_id = discovery["search_id"]
    for tool_id in discovery["tools"]:
        result = _call_tool(tool_id, search_id, parameters, max_response_size=max_response_size, timeout=timeout)
        if result and not _looks_like_error(result):
            return result
        logger.debug("Qveris: tool %s returned empty/error for query '%s', trying next", tool_id, query)
    return None


def _call_tool(tool_id: str, search_id: str, parameters: dict, max_response_size: int = 102400, timeout: int = 60) -> dict | None:
    """Execute a Qveris tool and return the result dict, or None on failure.

    Qveris wraps provider responses as {"status_code": N, "data": {...}}.
    When the data fits in the response, result["data"] holds the payload.
    When it is too large, result contains "truncated_content" (string) and
    "full_content_file_url".  We increase max_response_size to 100 KB by
    default to avoid truncation for typical financial statement responses.
    """
    try:
        data = _qveris_post(
            "/tools/execute",
            body={"search_id": search_id, "parameters": parameters, "max_response_size": max_response_size},
            query_params={"tool_id": tool_id},
            timeout=timeout,
        )
        if not data.get("success"):
            logger.warning("Qveris: tool %s reported failure: %s", tool_id, data.get("error_message"))
            return None
        raw = data.get("result") or {}
        # Unwrap Qveris envelope: {"status_code": N, "data": {...}}
        # The actual payload lives in raw["data"] when the provider response is
        # structured this way (Alpha Vantage, Twelve Data, etc.)
        if isinstance(raw.get("data"), dict):
            return raw["data"]
        # Fallback: return the raw result as-is (some providers put data at root)
        return raw
    except Exception as e:
        logger.warning("Qveris: call failed for tool %s: %s", tool_id, e)
        return None


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    f = _safe_float(val)
    return int(f) if f is not None else None


def _normalize_date(val) -> str | None:
    """Return an ISO date string (YYYY-MM-DD) from timestamps, strings, etc."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return None
    s = str(val)
    # Alpha Vantage compact format: "20250313T120000" or "20250313"
    if len(s) >= 8 and s[:8].isdigit() and (len(s) == 8 or s[8] in ("T", " ")):
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


def _get(d: dict, *keys):
    """Return the first value found in *d* for any of *keys*."""
    for k in keys:
        if k in d:
            return d[k]
    return None


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------
_PRICE_QUERY = "historical stock OHLCV daily price data by ticker and date range API"


def _parse_price_records(result: dict) -> list[dict]:
    for key in ("prices", "data", "results", "history", "candles", "bars", "ohlcv", "quotes", "timeSeries"):
        if key in result and isinstance(result[key], list):
            return result[key]
    # Alpha Vantage: {"Time Series (Daily)": {"2025-01-01": {...}}}
    for key, val in result.items():
        if "time series" in key.lower() and isinstance(val, dict):
            return [{"date": k, **v} for k, v in val.items()]
    if isinstance(result, list):
        return result
    return []


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    cache_key = f"{ticker}_{start_date}_{end_date}"
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**p) for p in cached_data]

    discovery = _discover_tools(_PRICE_QUERY)
    if not discovery:
        logger.warning("Qveris: no price tool found for %s", ticker)
        return []

    parameters = {
        "symbol": ticker,
        "ticker": ticker,
        "from": start_date,
        "to": end_date,
        "from_date": start_date,
        "to_date": end_date,
        "start_date": start_date,
        "end_date": end_date,
        # Tiingo uses startDate/endDate
        "startDate": start_date,
        "endDate": end_date,
        "interval": "1d",
        "period": "1d",
        "resampleFreq": "daily",
    }

    # Try each discovered tool until one returns actual price records
    records = []
    for tool_id in discovery["tools"]:
        result = _call_tool(tool_id, discovery["search_id"], parameters)
        if result:
            records = _parse_price_records(result)
            if records:
                break
        logger.debug("Qveris: price tool %s returned no records for %s, trying next", tool_id, ticker)
    prices = []
    for rec in records:
        time_val = _normalize_date(_get(rec, "date", "time", "t", "datetime", "timestamp", "Date"))
        if not time_val or time_val > end_date or time_val < start_date:
            continue
        close_val = _safe_float(_get(rec, "close", "c", "4. close", "Close", "closePrice", "price", "adjClose", "adjusted_close"))
        if close_val is None:
            continue
        prices.append(
            Price(
                open=_safe_float(_get(rec, "open", "o", "1. open", "Open", "openPrice")) or close_val,
                close=close_val,
                high=_safe_float(_get(rec, "high", "h", "2. high", "High", "highPrice")) or close_val,
                low=_safe_float(_get(rec, "low", "l", "3. low", "Low", "lowPrice")) or close_val,
                volume=_safe_int(_get(rec, "volume", "v", "5. volume", "Volume", "vol")) or 0,
                time=time_val,
            )
        )

    prices.sort(key=lambda p: p.time)
    if prices:
        _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


# ---------------------------------------------------------------------------
# Financial metrics
# ---------------------------------------------------------------------------
# Alpha Vantage OVERVIEW covers the broadest set of tickers including newer IPOs
_METRICS_QUERY = "company overview fundamental financial metrics PE ratio market cap earnings per share API"


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

    discovery = _discover_tool(_METRICS_QUERY)
    if not discovery:
        logger.warning("Qveris: no financial metrics tool found for %s", ticker)
        return []

    parameters = {"symbol": ticker, "ticker": ticker, "period": period, "function": "OVERVIEW"}
    result = _call_tool_any(_METRICS_QUERY, parameters)
    if not result:
        return []

    metrics = _parse_financial_metrics(ticker, end_date, period, result)
    if not metrics:
        return []

    metrics = metrics[:limit]
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics])
    return metrics


def _parse_financial_metrics(ticker: str, end_date: str, period: str, result: dict) -> list[FinancialMetrics]:
    # After _call_tool unwraps result.data, the payload may be at root (Alpha Vantage
    # OVERVIEW is flat) or nested under a key like "metrics"/"fundamentals"/"data".
    data = result
    for key in ("metrics", "financials", "fundamentals", "ratios", "overview"):
        if key in result:
            val = result[key]
            if isinstance(val, dict):
                data = val
                break
            if isinstance(val, list) and val:
                data = val[0]
                break
    # Alpha Vantage OVERVIEW uses "LatestQuarter" for the report date
    report_period = _normalize_date(
        _get(data, "LatestQuarter", "date", "report_period", "reportDate", "fiscalDateEnding")
    ) or end_date

    market_cap = _safe_float(_get(data, "MarketCapitalization", "marketCap", "market_cap", "mktCap", "marketCapitalization"))
    ev = _safe_float(_get(data, "enterpriseValue", "enterprise_value", "enterpriseVal", "EnterpriseValue"))
    # Alpha Vantage OVERVIEW: RevenueTTM
    revenue = _safe_float(_get(data, "RevenueTTM", "revenue", "totalRevenue", "total_revenue"))
    # Alpha Vantage OVERVIEW: EBITDA (absolute, not margin)
    ebitda = _safe_float(_get(data, "EBITDA", "ebitda"))
    fcf = _safe_float(_get(data, "freeCashFlow", "free_cash_flow", "fcf", "FreeCashFlow"))
    shares = _safe_float(_get(data, "SharesOutstanding", "sharesOutstanding", "shares_outstanding"))
    currency = str(_get(data, "Currency", "currency", "reportedCurrency") or "USD")

    ev_ebitda = _safe_float(_get(data, "EVToEBITDA", "evToEbitda", "ev_to_ebitda", "enterpriseValueMultiple"))
    if ev_ebitda is None and ev and ebitda and ebitda != 0:
        ev_ebitda = ev / ebitda

    ev_revenue = _safe_float(_get(data, "EVToRevenue", "evToRevenue", "ev_to_revenue"))
    if ev_revenue is None and ev and revenue and revenue != 0:
        ev_revenue = ev / revenue

    fcf_yield = _safe_float(_get(data, "fcfYield", "freeCashFlowYield"))
    if fcf_yield is None and fcf and market_cap and market_cap != 0:
        fcf_yield = fcf / market_cap

    fcf_per_share = _safe_float(_get(data, "fcfPerShare", "freeCashFlowPerShare"))
    if fcf_per_share is None and fcf and shares and shares != 0:
        fcf_per_share = fcf / shares

    de = _safe_float(_get(data, "debtToEquity", "debt_to_equity", "debtEquityRatio", "DebtToEquityRatioTTM"))
    if de is not None and de > 10:
        de = de / 100  # normalize percentage-style values

    # Alpha Vantage OVERVIEW: GrossProfitTTM is absolute dollars, not a margin ratio.
    # Compute margin = GrossProfitTTM / RevenueTTM when ratio-form is absent.
    gross_margin = _safe_float(_get(data, "grossMargin", "gross_margin", "grossMargins"))
    if gross_margin is None:
        gp = _safe_float(data.get("GrossProfitTTM"))
        if gp and revenue and revenue != 0:
            gross_margin = gp / revenue

    return [
        FinancialMetrics(
            ticker=ticker,
            report_period=report_period,
            period=period,
            currency=currency,
            market_cap=market_cap,
            enterprise_value=ev,
            # Alpha Vantage: PERatio / TrailingPE; others: pe, peRatio
            price_to_earnings_ratio=_safe_float(_get(data, "PERatio", "TrailingPE", "pe", "priceToEarnings", "peRatio", "trailingPE")),
            price_to_book_ratio=_safe_float(_get(data, "PriceToBookRatio", "pb", "priceToBook", "pbRatio")),
            price_to_sales_ratio=_safe_float(_get(data, "PriceToSalesRatioTTM", "ps", "priceToSales", "psRatio")),
            enterprise_value_to_ebitda_ratio=ev_ebitda,
            enterprise_value_to_revenue_ratio=ev_revenue,
            free_cash_flow_yield=fcf_yield,
            peg_ratio=_safe_float(_get(data, "PEGRatio", "peg", "pegRatio")),
            gross_margin=gross_margin,
            operating_margin=_safe_float(_get(data, "OperatingMarginTTM", "operatingMargin", "operating_margin", "operatingMargins")),
            net_margin=_safe_float(_get(data, "ProfitMargin", "netMargin", "net_margin", "profitMargins", "netProfitMargin")),
            return_on_equity=_safe_float(_get(data, "ReturnOnEquityTTM", "roe", "returnOnEquity", "return_on_equity")),
            return_on_assets=_safe_float(_get(data, "ReturnOnAssetsTTM", "roa", "returnOnAssets", "return_on_assets")),
            return_on_invested_capital=_safe_float(_get(data, "roic", "returnOnInvestedCapital", "return_on_invested_capital")),
            asset_turnover=_safe_float(_get(data, "assetTurnover", "asset_turnover", "AssetTurnover")),
            inventory_turnover=_safe_float(_get(data, "inventoryTurnover", "inventory_turnover", "InventoryTurnover")),
            receivables_turnover=_safe_float(_get(data, "receivablesTurnover", "receivables_turnover")),
            days_sales_outstanding=_safe_float(_get(data, "dso", "daysSalesOutstanding", "days_sales_outstanding")),
            operating_cycle=None,
            working_capital_turnover=None,
            current_ratio=_safe_float(_get(data, "currentRatio", "current_ratio", "CurrentRatio")),
            quick_ratio=_safe_float(_get(data, "quickRatio", "quick_ratio", "QuickRatio")),
            cash_ratio=_safe_float(_get(data, "cashRatio", "cash_ratio")),
            operating_cash_flow_ratio=None,
            debt_to_equity=de,
            debt_to_assets=_safe_float(_get(data, "debtToAssets", "debt_to_assets")),
            interest_coverage=_safe_float(_get(data, "interestCoverage", "interest_coverage")),
            revenue_growth=_safe_float(_get(data, "QuarterlyRevenueGrowthYOY", "revenueGrowth", "revenue_growth")),
            earnings_growth=_safe_float(_get(data, "QuarterlyEarningsGrowthYOY", "earningsGrowth", "earnings_growth")),
            book_value_growth=None,
            earnings_per_share_growth=None,
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=_safe_float(_get(data, "payoutRatio", "payout_ratio", "dividendPayoutRatio", "PayoutRatio")),
            earnings_per_share=_safe_float(_get(data, "EPS", "DilutedEPSTTM", "eps", "earningsPerShare", "trailingEps")),
            book_value_per_share=_safe_float(_get(data, "BookValue", "bvps", "bookValuePerShare", "bookValue")),
            free_cash_flow_per_share=fcf_per_share,
        )
    ]


# ---------------------------------------------------------------------------
# Line items — fetched from three separate Alpha Vantage endpoints and merged
# ---------------------------------------------------------------------------

# Which line items live in which statement
_INCOME_LINE_ITEMS = frozenset({
    "ebit", "ebitda", "interest_expense", "net_income", "revenue", "total_revenue",
    "gross_profit", "operating_income", "depreciation_and_amortization",
    "income_tax_expense", "research_and_development",
})
_CASHFLOW_LINE_ITEMS = frozenset({
    "free_cash_flow", "capital_expenditure", "depreciation_and_amortization",
    "operating_cash_flow", "stock_based_compensation",
})
_BALANCE_LINE_ITEMS = frozenset({
    "total_debt", "outstanding_shares", "total_assets", "total_liabilities",
    "cash_and_equivalents", "total_equity", "short_term_debt", "long_term_debt",
    "total_shareholder_equity",
})

_INCOME_QUERY = "income statement revenue EBIT interest expense earnings annual API"
_BALANCE_QUERY = "balance sheet total debt shares outstanding annual API"
_CASHFLOW_QUERY = "historical stock OHLCV daily price data by ticker and date range API"  # reuse price query cache slot; cash flow has its own below
_CF_QUERY = "company annual cash flow operating investing financing activities API"


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch requested line items by calling income, balance, and cash-flow endpoints
    separately via Qveris and merging the results by fiscal period date."""
    needed = set(line_items)
    need_income = bool(needed & _INCOME_LINE_ITEMS)
    need_balance = bool(needed & _BALANCE_LINE_ITEMS)
    need_cashflow = bool(needed & _CASHFLOW_LINE_ITEMS)

    # date → dict of field values
    merged: dict[str, dict] = {}

    if need_income:
        _fetch_income_statement(ticker, end_date, limit, merged)
    if need_balance:
        _fetch_balance_sheet(ticker, end_date, limit, merged)
    if need_cashflow:
        _fetch_cash_flow(ticker, end_date, limit, merged)

    if not merged:
        return []

    output = []
    for report_period in sorted(merged.keys(), reverse=True)[:limit]:
        if report_period > end_date:
            continue
        row = merged[report_period]
        currency = row.get("_currency", "USD")
        data: dict = {"ticker": ticker, "report_period": report_period, "period": period, "currency": currency}
        for item in line_items:
            data[item] = row.get(item)
        output.append(LineItem(**data))

    return output


def _av_records(ticker: str, function: str, query: str) -> list[dict]:
    """Fetch annualReports from an Alpha Vantage-style endpoint via Qveris,
    trying each discovered tool in turn until one returns actual report data.

    Some providers (TwelveData) return a success envelope wrapping an error body
    like {"code": ..., "message": ..., "status": "error"} for unknown tickers.
    We skip those and fall through to the next candidate tool.
    """
    discovery = _discover_tools(query)
    if not discovery:
        return []
    search_id = discovery["search_id"]
    for tool_id in discovery["tools"]:
        result = _call_tool(tool_id, search_id, {"symbol": ticker, "function": function})
        if not isinstance(result, dict) or _looks_like_error(result):
            logger.debug("Qveris: tool %s returned error/empty for %s/%s, trying next", tool_id, ticker, function)
            continue
        records = result.get("annualReports") or result.get("quarterlyReports") or []
        if records:
            return records
        # Handle Twelve Data / other flat-list formats
        for key in ("income_statement", "balance_sheet", "cash_flow", "financials", "data", "results"):
            val = result.get(key)
            if isinstance(val, list) and val and isinstance(val[0], dict):
                return val
        logger.debug("Qveris: tool %s returned no records for %s/%s, trying next", tool_id, ticker, function)
    return []


def _fetch_income_statement(ticker: str, end_date: str, limit: int, merged: dict) -> None:
    for rec in _av_records(ticker, "INCOME_STATEMENT", _INCOME_QUERY)[:limit]:
        dt = _normalize_date(_get(rec, "fiscalDateEnding", "date", "fiscal_date"))
        if not dt or dt > end_date:
            continue
        row = merged.setdefault(dt, {})
        row["_currency"] = str(_get(rec, "reportedCurrency") or "USD")
        # Alpha Vantage income statement field names
        row["ebit"] = _safe_float(_get(rec, "ebit", "operatingIncome"))
        row["ebitda"] = _safe_float(rec.get("ebitda"))
        row["interest_expense"] = _safe_float(_get(rec, "interestExpense", "interestAndDebtExpense"))
        row["net_income"] = _safe_float(rec.get("netIncome"))
        row["revenue"] = _safe_float(_get(rec, "totalRevenue", "revenue"))
        row["total_revenue"] = row["revenue"]
        row["gross_profit"] = _safe_float(rec.get("grossProfit"))
        row["operating_income"] = _safe_float(rec.get("operatingIncome"))
        row["depreciation_and_amortization"] = _safe_float(
            _get(rec, "depreciationAndAmortization", "depreciation")
        )
        row["income_tax_expense"] = _safe_float(rec.get("incomeTaxExpense"))
        row["research_and_development"] = _safe_float(rec.get("researchAndDevelopment"))


def _fetch_balance_sheet(ticker: str, end_date: str, limit: int, merged: dict) -> None:
    for rec in _av_records(ticker, "BALANCE_SHEET", _BALANCE_QUERY)[:limit]:
        dt = _normalize_date(_get(rec, "fiscalDateEnding", "date", "fiscal_date"))
        if not dt or dt > end_date:
            continue
        row = merged.setdefault(dt, {})
        row.setdefault("_currency", str(_get(rec, "reportedCurrency") or "USD"))
        row["total_assets"] = _safe_float(rec.get("totalAssets"))
        row["total_liabilities"] = _safe_float(rec.get("totalLiabilities"))
        row["total_equity"] = _safe_float(rec.get("totalShareholderEquity"))
        row["total_shareholder_equity"] = row["total_equity"]
        row["short_term_debt"] = _safe_float(_get(rec, "shortTermDebt", "currentDebt"))
        row["long_term_debt"] = _safe_float(_get(rec, "longTermDebt", "longTermDebtNoncurrent"))
        # Alpha Vantage: shortLongTermDebtTotal = short + long combined
        total_debt = _safe_float(rec.get("shortLongTermDebtTotal"))
        if total_debt is None:
            st = row.get("short_term_debt") or 0
            lt = row.get("long_term_debt") or 0
            total_debt = (st + lt) if (st or lt) else None
        row["total_debt"] = total_debt
        row["cash_and_equivalents"] = _safe_float(
            _get(rec, "cashAndCashEquivalentsAtCarryingValue", "cashAndShortTermInvestments")
        )
        row["outstanding_shares"] = _safe_float(rec.get("commonStockSharesOutstanding"))


def _fetch_cash_flow(ticker: str, end_date: str, limit: int, merged: dict) -> None:
    for rec in _av_records(ticker, "CASH_FLOW", _CF_QUERY)[:limit]:
        dt = _normalize_date(_get(rec, "fiscalDateEnding", "date", "fiscal_date"))
        if not dt or dt > end_date:
            continue
        row = merged.setdefault(dt, {})
        row.setdefault("_currency", str(_get(rec, "reportedCurrency") or "USD"))
        op_cf = _safe_float(rec.get("operatingCashflow"))
        capex = _safe_float(rec.get("capitalExpenditures"))
        row["operating_cash_flow"] = op_cf
        row["capital_expenditure"] = capex
        row["stock_based_compensation"] = _safe_float(rec.get("stockBasedCompensation"))
        row["depreciation_and_amortization"] = row.get("depreciation_and_amortization") or _safe_float(
            rec.get("depreciationDepletionAndAmortization")
        )
        # FCF = operating CF - capex
        if op_cf is not None and capex is not None:
            row["free_cash_flow"] = op_cf - capex
        elif op_cf is not None:
            row["free_cash_flow"] = op_cf
        # Prefer income statement net_income; fall back to cash flow
        if row.get("net_income") is None:
            row["net_income"] = _safe_float(rec.get("netIncome"))


# ---------------------------------------------------------------------------
# Insider trades
# ---------------------------------------------------------------------------
_INSIDER_QUERY = "SEC insider trading transactions Form 4 stock ownership filing data API"


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

    discovery = _discover_tool(_INSIDER_QUERY)
    if not discovery:
        logger.warning("Qveris: no insider trades tool found for %s", ticker)
        return []

    parameters: dict = {"symbol": ticker, "ticker": ticker, "limit": limit, "to_date": end_date, "to": end_date}
    if start_date:
        parameters["from_date"] = start_date
        parameters["from"] = start_date

    result = _call_tool(discovery["tool_id"], discovery["search_id"], parameters)
    if not result:
        return []

    trades = _parse_insider_trades(ticker, end_date, start_date, limit, result)
    if trades:
        _cache.set_insider_trades(cache_key, [t.model_dump() for t in trades])
    return trades


def _parse_insider_trades(ticker: str, end_date: str, start_date: str | None, limit: int, result: dict) -> list[InsiderTrade]:
    records = None
    for key in ("insider_trades", "insiderTransactions", "transactions", "data", "results", "insiders"):
        if key in result and isinstance(result[key], list):
            records = result[key]
            break
    if not records:
        return []

    trades = []
    for rec in records:
        filing_date = _normalize_date(_get(rec, "filingDate", "filing_date", "date", "transactionDate", "reportDate"))
        if not filing_date:
            continue
        if filing_date > end_date:
            continue
        if start_date and filing_date < start_date:
            continue

        shares = _safe_float(_get(rec, "shares", "transactionShares", "transaction_shares", "sharesTraded", "numberOfShares"))
        value = _safe_float(_get(rec, "value", "transactionValue", "transaction_value", "totalValue", "transactionAmount"))
        price = _safe_float(_get(rec, "price", "transactionPrice", "pricePerShare", "sharePrice"))
        if price is None and value and shares and shares != 0:
            price = value / shares

        trades.append(
            InsiderTrade(
                ticker=ticker,
                issuer=str(_get(rec, "issuer", "company", "companyName", "issuerName") or ticker),
                name=str(_get(rec, "name", "insiderName", "insider_name", "reportingOwnerName", "insider") or ""),
                title=str(_get(rec, "title", "position", "officerTitle", "relationship", "ownerTitle") or ""),
                is_board_director=None,
                transaction_date=_normalize_date(_get(rec, "transactionDate", "transaction_date", "tradeDate", "date")) or filing_date,
                transaction_shares=shares,
                transaction_price_per_share=price,
                transaction_value=value,
                shares_owned_before_transaction=_safe_float(_get(rec, "sharesBefore", "sharesOwnedBefore", "shares_owned_before")),
                shares_owned_after_transaction=_safe_float(_get(rec, "sharesAfter", "sharesOwnedAfter", "shares_owned_after", "sharesTotal", "totalShares")),
                security_title=str(_get(rec, "securityTitle", "security_title", "securityType", "securityName") or ""),
                filing_date=filing_date,
            )
        )

        if len(trades) >= limit:
            break

    return trades


# ---------------------------------------------------------------------------
# Company news
# ---------------------------------------------------------------------------
_NEWS_QUERY = "company stock financial news articles headlines sentiment API"


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

    discovery = _discover_tools(_NEWS_QUERY)
    if not discovery:
        logger.warning("Qveris: no news tool found for %s", ticker)
        return []

    parameters: dict = {
        # Alpha Vantage NEWS_SENTIMENT uses "tickers" and "function"
        "tickers": ticker,
        "function": "NEWS_SENTIMENT",
        # Generic alternatives used by other providers
        "symbol": ticker,
        "ticker": ticker,
        "symbols": ticker,
        "q": ticker,
        "keywords": ticker,
        "limit": min(limit, 100),
        "page_size": min(limit, 100),
        "to_date": end_date,
        "to": end_date,
        "time_to": end_date,
    }
    if start_date:
        parameters["from_date"] = start_date
        parameters["from"] = start_date
        parameters["time_from"] = start_date

    news_items = []
    logger.info("Qveris: trying %d news tools for %s", len(discovery["tools"]), ticker)
    for tool_id in discovery["tools"]:
        result = _call_tool(tool_id, discovery["search_id"], parameters)
        if not result or _looks_like_error(result):
            logger.info("Qveris: news tool %s returned error/empty for %s, trying next", tool_id, ticker)
            continue
        top_keys = list(result.keys())[:5]
        logger.info("Qveris: news tool %s raw keys for %s: %s", tool_id, ticker, top_keys)
        news_items = _parse_company_news(ticker, end_date, start_date, limit, result)
        if news_items:
            logger.info("Qveris: news tool %s returned %d articles for %s", tool_id, len(news_items), ticker)
            break
        logger.info("Qveris: news tool %s returned 0 parsed articles for %s (raw keys: %s), trying next", tool_id, ticker, top_keys)
    if news_items:
        _cache.set_company_news(cache_key, [n.model_dump() for n in news_items])
    return news_items


def _parse_company_news(ticker: str, end_date: str, start_date: str | None, limit: int, result: dict) -> list[CompanyNews]:
    records = None
    for key in ("news", "articles", "data", "results", "feed", "items", "stories"):
        if key in result and isinstance(result[key], list):
            records = result[key]
            break
    if not records:
        return []

    items = []
    for rec in records:
        date_raw = _get(rec, "date", "publishedAt", "publishDate", "time_published", "pubDate", "datetime", "timestamp", "providerPublishTime", "published_at")
        date_str = _normalize_date(date_raw) or end_date

        if date_str > end_date:
            continue
        if start_date and date_str < start_date:
            continue

        sentiment_raw = _get(rec, "sentiment", "overall_sentiment_label", "sentimentLabel", "overall_sentiment")
        if sentiment_raw:
            sl = str(sentiment_raw).lower().replace("-", "_").replace(" ", "_")
            if "bullish" in sl or sl in ("positive", "buy", "strong_buy"):
                sentiment = "positive"
            elif "bearish" in sl or sl in ("negative", "sell", "strong_sell"):
                sentiment = "negative"
            else:
                sentiment = "neutral"
        else:
            sentiment = None

        items.append(
            CompanyNews(
                ticker=ticker,
                title=str(_get(rec, "title", "headline", "summary", "name") or ""),
                author=str(_get(rec, "author", "authors", "source_authors", "byline", "creator") or ""),
                source=str(_get(rec, "source", "publisher", "provider", "domain", "feed", "site") or ""),
                date=date_str,
                url=str(_get(rec, "url", "link", "articleUrl", "article_url", "storyUrl") or ""),
                sentiment=sentiment,
            )
        )

        if len(items) >= limit:
            break

    return items


# ---------------------------------------------------------------------------
# Market cap
# ---------------------------------------------------------------------------
_MKTCAP_QUERY = "company overview fundamental financial metrics PE ratio market cap earnings per share API"


def get_market_cap(ticker: str, end_date: str, api_key: str = None) -> float | None:
    # Reuse the same OVERVIEW endpoint as get_financial_metrics for consistency
    discovery = _discover_tool(_MKTCAP_QUERY)
    if not discovery:
        logger.warning("Qveris: no market-cap tool found for %s", ticker)
        return None

    result = _call_tool_any(_MKTCAP_QUERY, {"symbol": ticker, "ticker": ticker, "function": "OVERVIEW"})
    if not result:
        return None

    # Alpha Vantage OVERVIEW: MarketCapitalization; others: marketCap / market_cap
    mktcap = _safe_float(_get(result, "MarketCapitalization", "marketCap", "market_cap", "marketCapitalization", "mktCap"))
    if mktcap:
        return mktcap

    # Last resort: pull from financial metrics
    metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    return metrics[0].market_cap if metrics else None


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
