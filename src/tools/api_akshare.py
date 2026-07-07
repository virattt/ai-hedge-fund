"""A-share data layer backed by akshare.

All public functions mirror the signatures in ``src/tools/api.py`` so they are
true drop-ins. The dispatch lives at the top of each function in ``api.py``:

    if is_a_share(ticker):
        from src.tools import api_akshare
        return api_akshare.<func>(...)

Conventions:
- A-share tickers arrive in Tushare format (``600519.SH``). We convert to the
  bare 6-digit code via :func:`src.tools.markets.a_share_code` before calling
  akshare.
- Every function returns ``[]`` / ``None`` on failure (mirrors US behaviour).
- The Pydantic models from :mod:`src.data.models` are the return element types.
"""
from __future__ import annotations

import datetime
import logging
import random
import time
from typing import Callable, TypeVar

import akshare as ak
import pandas as pd

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)
from src.tools.markets import a_share_code

logger = logging.getLogger(__name__)

# Global cache instance (same one used by api.py — in-memory, shared)
_cache = get_cache()

# Process-wide memo for the all-market spot table returned by
# ``stock_zh_a_spot_em``. That endpoint ships *every* A-share (~5,000 rows) in
# one call, so we fetch it once and look each ticker up from the shared table.
# Without this, the concurrent analyst fan-out fires the heavy endpoint once
# per agent per ticker and Eastmoney rate-limits the run — closing the
# connection mid-flight (``RemoteDisconnected``). Guarded by ``fetch_lock`` so
# simultaneous misses serialise to a single network call.
_spot_table: pd.DataFrame | None = None

T = TypeVar("T")


def _with_retry(
    fn: Callable[[], T],
    retries: int = 1,
    delay: float = 2.0,
    backoff: float = 2.0,
    jitter: float = 0.0,
) -> T:
    """Call ``fn`` with retries on common akshare transient errors.

    Waits ``delay * backoff**attempt`` before retry number ``attempt + 1``, plus
    up to ``jitter`` seconds of randomness. The jitter desyncs concurrent
    retries so a roomful of agents rate-limited at the same instant don't all
    wake up together and get dropped again — relevant for the shared spot-table
    fetch, which is the single gating call for every ticker's market cap.

    akshare already does some internal rate-limit handling, so the defaults
    (``retries=1``, ``jitter=0``) preserve the original one-retry-after-``delay``
    behaviour for the existing per-ticker callers; the spot-table fetch asks
    for ``retries=3`` with jitter.

    Retries on ``JSONDecodeError``, ``ConnectionError``, ``RemoteDisconnected``,
    ``TimeoutError`` or an empty DataFrame result. Any other exception
    propagates immediately (the caller wraps in try/except and returns
    ``[]``/``None``).
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            result = fn()
        except Exception as e:  # noqa: BLE001 - akshare raises a wide variety
            msg = str(e).lower()
            transient = any(
                token in msg
                for token in ("jsondecodeerror", "connection", "remotedisconnected", "timeout")
            ) or isinstance(e, (ConnectionError, TimeoutError))
            if transient and attempt < retries:
                wait = delay * (backoff ** attempt) + random.uniform(0, jitter)
                logger.warning(
                    "akshare transient error for %s: %s — retrying after %.1fs",
                    getattr(fn, "__name__", fn),
                    e,
                    wait,
                )
                last_exc = e
                time.sleep(wait)
                continue
            raise
        else:
            # Treat empty DataFrame as a transient signal worth one retry
            if isinstance(result, pd.DataFrame) and result.empty and attempt < retries:
                wait = delay * (backoff ** attempt) + random.uniform(0, jitter)
                logger.warning("akshare returned empty DataFrame — retrying after %.1fs", wait)
                time.sleep(wait)
                continue
            return result
    # All retries exhausted: re-raise the last transient exception
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------------------
# 1. Prices
# ---------------------------------------------------------------------------
def get_prices(
    ticker: str,
    start_date: str,
    end_date: str,
    api_key: str | None = None,
) -> list[Price]:
    """Fetch daily OHLCV via ``akshare.stock_zh_a_hist`` (forward-adjusted)."""
    cache_key = f"{ticker}_{start_date}_{end_date}"
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    code = a_share_code(ticker)
    start_ak = start_date.replace("-", "")
    end_ak = end_date.replace("-", "")

    def _fetch() -> pd.DataFrame:
        try:
            return ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_ak,
                end_date=end_ak,
                adjust="qfq",
            )
        except Exception:
            # Fallback: raw (unadjusted) prices
            return ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_ak,
                end_date=end_ak,
                adjust="",
            )

    try:
        df = _with_retry(_fetch)
    except Exception as e:
        logger.warning("akshare get_prices failed for %s: %s", ticker, e)
        return []

    if df is None or df.empty:
        return []

    # Column map: 日期/开盘/收盘/最高/最低/成交量/成交额/振幅/涨跌幅/涨跌额/换手率
    col_map = {
        "日期": "time",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
    }
    df = df.rename(columns=col_map)

    prices: list[Price] = []
    for _, row in df.iterrows():
        try:
            prices.append(
                Price(
                    time=str(row["time"]),
                    open=float(row["open"]),
                    close=float(row["close"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    volume=int(row["volume"]),
                )
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("skipping bad price row for %s: %s", ticker, e)
            continue

    if not prices:
        return []

    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


# ---------------------------------------------------------------------------
# 2. Financial metrics
# ---------------------------------------------------------------------------
def _safe_float(val) -> float | None:
    if val is None or pd.isna(val):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pct_to_decimal(val) -> float | None:
    """Convert an akshare percent number (e.g. 32.53 meaning 32.53%) to a
    decimal ratio (0.3253).

    ``stock_financial_abstract`` returns ratios/margins/growth rates as percent
    numbers. The project's :class:`FinancialMetrics` model expects decimal
    ratios. Fields that are already dimensionless ratios (e.g. current_ratio =
    3.5 meaning 3.5:1) must NOT be passed through this helper.
    """
    f = _safe_float(val)
    if f is None:
        return None
    return f / 100.0


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str | None = None,
) -> list[FinancialMetrics]:
    """Fetch financial metrics via ``akshare.stock_financial_abstract``.

    ``stock_financial_analysis_indicator`` has become flaky in recent akshare
    releases; we fall back to ``stock_financial_abstract`` which exposes a
    transposed report (rows = indicator names, columns = report periods).
    """
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**m) for m in cached_data]

    code = a_share_code(ticker)

    def _fetch() -> pd.DataFrame:
        return ak.stock_financial_abstract(symbol=code)

    try:
        df = _with_retry(_fetch)
    except Exception as e:
        logger.warning("akshare get_financial_metrics failed for %s: %s", ticker, e)
        return []

    if df is None or df.empty:
        return []

    # Transpose: indicator name -> row index, then pivot so each report period
    # becomes one record. Columns after position 1 are report periods (YYYYMMDD).
    period_cols = [c for c in df.columns if c not in ("选项", "指标")]
    # Build lookup: indicator -> {period: value}
    lookup: dict[str, dict[str, float]] = {}
    for _, row in df.iterrows():
        ind = row["指标"]
        if not isinstance(ind, str):
            continue
        per_vals: dict[str, float] = {}
        for pc in period_cols:
            per_vals[pc] = _safe_float(row[pc])
        # Later rows with the same indicator name overwrite earlier ones
        # (akshare often repeats e.g. 毛利率 in different sections; latest wins)
        lookup.setdefault(ind, {}).update(per_vals)

    # Filter report periods to those <= end_date
    end_norm = end_date.replace("-", "")
    eligible = sorted(
        (pc for pc in period_cols if pc and pc <= end_norm),
        reverse=True,
    )[:limit]
    if not eligible:
        return []

    def _get(ind: str, pc: str) -> float | None:
        return lookup.get(ind, {}).get(pc)

    # Percentage fields returned by stock_financial_abstract as percent numbers
    # (e.g. 32.53 meaning 32.53%). These must be divided by 100 to produce the
    # decimal ratios that FinancialMetrics expects.
    def _pct(ind: str, pc: str) -> float | None:
        return _pct_to_decimal(_get(ind, pc))

    metrics: list[FinancialMetrics] = []
    for pc in eligible:
        report_period = f"{pc[:4]}-{pc[4:6]}-{pc[6:]}"
        metrics.append(
            FinancialMetrics(
                ticker=ticker,
                report_period=report_period,
                period=period,
                currency="CNY",
                market_cap=None,  # handled separately in get_market_cap
                enterprise_value=None,
                price_to_earnings_ratio=None,
                price_to_book_ratio=None,
                price_to_sales_ratio=None,
                enterprise_value_to_ebitda_ratio=None,
                enterprise_value_to_revenue_ratio=None,
                free_cash_flow_yield=None,
                peg_ratio=None,
                # --- percentage fields (divide by 100) ---
                gross_margin=_pct("毛利率", pc),
                operating_margin=_pct("营业利润率", pc),
                net_margin=_pct("销售净利率", pc),
                return_on_equity=_pct("净资产收益率(ROE)", pc),
                return_on_assets=_pct("总资产报酬率", pc),
                return_on_invested_capital=_pct("投入资本回报率", pc),
                debt_to_equity=_pct("产权比率", pc),
                debt_to_assets=_pct("资产负债率", pc),
                revenue_growth=_pct("营业总收入增长率", pc),
                earnings_growth=_pct("归属母公司净利润增长率", pc),
                # --- ratio fields (already dimensionless, do NOT divide) ---
                asset_turnover=_get("总资产周转率", pc),
                inventory_turnover=_get("存货周转率", pc),
                receivables_turnover=_get("应收账款周转率", pc),
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                current_ratio=_get("流动比率", pc),
                quick_ratio=_get("速动比率", pc),
                cash_ratio=_get("现金比率", pc),
                operating_cash_flow_ratio=None,
                interest_coverage=None,
                book_value_growth=None,
                earnings_per_share_growth=None,
                free_cash_flow_growth=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=None,
                # --- per-share values (absolute, not ratios) ---
                earnings_per_share=_get("基本每股收益", pc),
                book_value_per_share=_get("每股净资产", pc),
                free_cash_flow_per_share=_get("每股企业自由现金流量", pc),
            )
        )

    if not metrics:
        return []

    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics])
    return metrics


# ---------------------------------------------------------------------------
# 3. Line items
# ---------------------------------------------------------------------------

# Each English line-item name maps to a **list** of candidate Chinese column
# names across the three statements (first match wins). Sources:
#   - 利润表 (income statement)   via stock_financial_report_sina
#   - 资产负债表 (balance sheet)  via stock_financial_report_sina
#   - 现金流量表 (cash flow)      via stock_financial_report_sina
_LINE_ITEM_MAP: dict[str, list[str]] = {
    # --- income statement fields ---
    "revenue": ["营业收入", "营业总收入"],
    "operating_income": ["营业利润"],
    "operating_expense": ["营业成本"],  # COGS — closest match
    "gross_profit": ["毛利"],  # may not exist as a column; computed below
    "net_income": ["归属于母公司所有者的净利润", "净利润"],
    "earnings_per_share": ["基本每股收益"],
    "research_and_development": ["研发费用"],
    "interest_expense": ["利息支出", "利息费用", "财务费用"],
    # --- balance sheet fields ---
    "total_assets": ["资产总计"],
    "current_assets": ["流动资产合计"],
    "current_liabilities": ["流动负债合计"],
    "total_liabilities": ["负债合计"],
    "shareholders_equity": [
        "归属于母公司股东权益合计",
        "所有者权益(或股东权益)合计",
    ],
    "cash_and_equivalents": ["货币资金"],
    "intangible_assets": ["无形资产"],
    "goodwill_and_intangible_assets": ["商誉", "无形资产"],  # sum if both present
    "total_debt": ["短期借款", "长期借款"],  # sum of short-term + long-term debt
    "outstanding_shares": ["实收资本(或股本)"],
    "book_value_per_share": ["每股净资产"],
    # --- cash flow statement fields ---
    "capital_expenditure": [
        "购建固定资产、无形资产和其他长期资产所支付的现金",
    ],
    "depreciation_and_amortization": [
        "固定资产折旧",  # may not be directly in the statement
    ],
    "dividends_and_other_cash_distributions": [
        "分配股利、利润或偿付利息所支付的现金",
    ],
    "issuance_or_purchase_of_equity_shares": [
        "吸收投资收到的现金",
    ],
}

# In-process cache for the three statements per (ticker, end_date).
# An agent run hits search_line_items ~14 times per ticker; this cache means
# we only do 3 HTTP fetches total instead of 42.
_statement_cache: dict[tuple[str, str], dict[str, pd.DataFrame]] = {}


def _fetch_statements(ticker: str, end_date: str) -> dict[str, pd.DataFrame]:
    """Fetch and cache the three Chinese financial statements for ``ticker``.

    Returns a dict with keys ``"income"``, ``"balance"``, ``"cashflow"``.
    Missing statements are omitted from the dict (caller checks with ``.get``).
    """
    cache_key = (ticker, end_date)
    if cache_key in _statement_cache:
        return _statement_cache[cache_key]

    code = a_share_code(ticker)
    # Sina uses sh/sz prefix
    if ticker.endswith(".SH"):
        sina_stock = f"sh{code}"
    elif ticker.endswith(".SZ"):
        sina_stock = f"sz{code}"
    elif ticker.endswith(".BJ"):
        sina_stock = f"bj{code}"
    else:
        sina_stock = code

    statements: dict[str, pd.DataFrame] = {}

    for key, symbol in [
        ("income", "利润表"),
        ("balance", "资产负债表"),
        ("cashflow", "现金流量表"),
    ]:
        def _fetch() -> pd.DataFrame:
            return ak.stock_financial_report_sina(stock=sina_stock, symbol=symbol)

        try:
            df = _with_retry(_fetch)
            if df is not None and not df.empty:
                statements[key] = df
        except Exception as e:
            logger.warning(
                "akshare search_line_items: failed to fetch %s for %s: %s",
                symbol,
                ticker,
                e,
            )
        # Rate-limit between statement fetches
        time.sleep(0.3)

    _statement_cache[cache_key] = statements
    return statements


def _extract_value(
    statement: pd.DataFrame | None,
    candidates: list[str],
    report_date: str,
) -> float | None:
    """Look up a value from a statement by trying candidate column names.

    ``report_date`` is a normalised ``YYYYMMDD`` string matching the ``报告日``
    column. Returns the first successful match or ``None``.
    """
    if statement is None or report_date is None:
        return None
    for col in candidates:
        if col not in statement.columns:
            continue
        row = statement[statement["报告日"] == report_date]
        if row.empty:
            continue
        return _safe_float(row.iloc[0][col])
    return None


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str | None = None,
) -> list[LineItem]:
    """Fetch line items for A-shares via ``akshare.stock_financial_report_sina``.

    Maps the 30 project-level English line-item names to Chinese column names
    in the three financial statements (income / balance / cash flow).

    **Period limitation**: ``stock_financial_report_sina`` returns all report
    periods (quarterly + annual). For ``period="annual"`` only year-end
    (``12-31``) periods are returned. For ``period="ttm"`` or
    ``period="quarterly"`` we fall back to annual data — proper TTM math
    would need 4-quarter rolling calculations and is out of scope for this PR.

    Results are sorted most-recent-first and capped at ``limit``. Periods
    after ``end_date`` are filtered out.
    """
    if not line_items:
        return []

    statements = _fetch_statements(ticker, end_date)
    if not statements:
        return []

    income_df = statements.get("income")
    balance_df = statements.get("balance")
    cashflow_df = statements.get("cashflow")

    # Collect all available report periods from the income statement (primary).
    # Fall back to balance or cash flow if income is missing.
    primary = None
    for candidate in (income_df, balance_df, cashflow_df):
        if candidate is not None and not candidate.empty:
            primary = candidate
            break
    if primary is None:
        return []

    all_dates = set(primary["报告日"].tolist())
    for df in (balance_df, cashflow_df):
        if df is not None:
            all_dates.update(df["报告日"].tolist())

    end_norm = end_date.replace("-", "")

    if period == "annual":
        eligible = sorted(
            (d for d in all_dates if d and d <= end_norm and d.endswith("1231")),
            reverse=True,
        )
    else:
        # TTM / quarterly: fall back to annual data (documented limitation).
        # We still only use year-end periods to avoid mixing Q1/Q3 cumulative
        # data which would produce nonsensical values.
        eligible = sorted(
            (d for d in all_dates if d and d <= end_norm and d.endswith("1231")),
            reverse=True,
        )

    eligible = eligible[:limit]
    if not eligible:
        return []

    results: list[LineItem] = []
    for report_date_norm in eligible:
        report_period = (
            f"{report_date_norm[:4]}-{report_date_norm[4:6]}-{report_date_norm[6:]}"
        )

        # Initialise all requested fields to None so that agents can safely
        # access them via attribute lookup (e.g. ``fi.total_debt is not None``)
        # without triggering AttributeError on the Pydantic model. Without
        # this, accessing an unset extra field raises AttributeError even
        # though model_config allows extra fields.
        fields: dict[str, float | None] = {name: None for name in line_items}

        for item_name in line_items:
            candidates = _LINE_ITEM_MAP.get(item_name)
            if candidates is None:
                continue

            # Determine which statement to look in based on the field type.
            # We try all three statements — first match wins.
            val = None
            for stmt in (income_df, balance_df, cashflow_df):
                val = _extract_value(stmt, candidates, report_date_norm)
                if val is not None:
                    break

            if val is not None:
                fields[item_name] = val

        # --- Computed / derived fields ---
        # These override direct lookups if the underlying components are present.

        # goodwill_and_intangible_assets = goodwill + intangibles
        if "goodwill_and_intangible_assets" in line_items:
            gw = _extract_value(balance_df, ["商誉"], report_date_norm) or 0.0
            ia = _extract_value(balance_df, ["无形资产"], report_date_norm) or 0.0
            if gw or ia:
                fields["goodwill_and_intangible_assets"] = gw + ia

        # total_debt = short-term + long-term borrowing + bonds
        if "total_debt" in line_items:
            short_debt = _extract_value(
                balance_df, ["短期借款"], report_date_norm
            ) or 0.0
            long_debt = _extract_value(
                balance_df, ["长期借款"], report_date_norm
            ) or 0.0
            bonds = _extract_value(
                balance_df, ["应付债券"], report_date_norm
            ) or 0.0
            total = short_debt + long_debt + bonds
            fields["total_debt"] = total if total > 0 else None

        # working_capital = current_assets - current_liabilities
        if "working_capital" in line_items:
            ca = _extract_value(balance_df, ["流动资产合计"], report_date_norm)
            cl = _extract_value(balance_df, ["流动负债合计"], report_date_norm)
            if ca is not None and cl is not None:
                fields["working_capital"] = ca - cl

        # free_cash_flow = operating_cash_flow - capex
        if "free_cash_flow" in line_items:
            ocf = _extract_value(
                cashflow_df, ["经营活动产生的现金流量净额"], report_date_norm
            )
            capex = _extract_value(
                cashflow_df,
                ["购建固定资产、无形资产和其他长期资产所支付的现金"],
                report_date_norm,
            )
            if ocf is not None and capex is not None:
                fields["free_cash_flow"] = ocf - capex
            elif ocf is not None:
                # If capex missing, at least set OCF as a rough proxy
                fields["free_cash_flow"] = ocf

        # gross_profit = revenue - operating_expense (COGS)
        if "gross_profit" in line_items:
            rev = _extract_value(income_df, ["营业收入", "营业总收入"], report_date_norm)
            cogs = _extract_value(income_df, ["营业成本"], report_date_norm)
            if rev is not None and cogs is not None:
                fields["gross_profit"] = rev - cogs

        # gross_margin = gross_profit / revenue  (decimal ratio)
        if "gross_margin" in line_items:
            rev = _extract_value(income_df, ["营业收入", "营业总收入"], report_date_norm)
            cogs = _extract_value(income_df, ["营业成本"], report_date_norm)
            if rev is not None and cogs is not None and rev != 0:
                fields["gross_margin"] = (rev - cogs) / rev

        # operating_margin = operating_income / revenue  (decimal ratio)
        if "operating_margin" in line_items:
            op_income = _extract_value(income_df, ["营业利润"], report_date_norm)
            rev = _extract_value(income_df, ["营业收入", "营业总收入"], report_date_norm)
            if op_income is not None and rev is not None and rev != 0:
                fields["operating_margin"] = op_income / rev

        # debt_to_equity = total_debt / shareholders_equity  (decimal ratio)
        if "debt_to_equity" in line_items:
            short_debt = _extract_value(
                balance_df, ["短期借款"], report_date_norm
            ) or 0.0
            long_debt = _extract_value(
                balance_df, ["长期借款"], report_date_norm
            ) or 0.0
            bonds = _extract_value(
                balance_df, ["应付债券"], report_date_norm
            ) or 0.0
            equity = _extract_value(
                balance_df,
                ["归属于母公司股东权益合计", "所有者权益(或股东权益)合计"],
                report_date_norm,
            )
            total_debt_val = short_debt + long_debt + bonds
            if equity is not None and equity != 0 and total_debt_val > 0:
                fields["debt_to_equity"] = total_debt_val / equity

        # return_on_invested_capital = net_income / (debt + equity)
        # (simplified ROIC approximation)
        if "return_on_invested_capital" in line_items:
            ni = _extract_value(
                income_df,
                ["归属于母公司所有者的净利润", "净利润"],
                report_date_norm,
            )
            short_debt = _extract_value(
                balance_df, ["短期借款"], report_date_norm
            ) or 0.0
            long_debt = _extract_value(
                balance_df, ["长期借款"], report_date_norm
            ) or 0.0
            bonds = _extract_value(
                balance_df, ["应付债券"], report_date_norm
            ) or 0.0
            equity = _extract_value(
                balance_df,
                ["归属于母公司股东权益合计", "所有者权益(或股东权益)合计"],
                report_date_norm,
            )
            invested = short_debt + long_debt + bonds + (equity or 0)
            if ni is not None and invested > 0:
                fields["return_on_invested_capital"] = ni / invested

        # ebit: Chinese 营业利润 (operating profit) is the closest analogue.
        # Under post-2017 PRC accounting standards, 营业利润 excludes interest
        # expense for non-financial firms, making it a reasonable EBIT proxy.
        if "ebit" in line_items:
            op_income = _extract_value(income_df, ["营业利润"], report_date_norm)
            if op_income is not None:
                fields["ebit"] = op_income

        # ebitda = ebit + depreciation_and_amortization
        if "ebitda" in line_items:
            op_income = _extract_value(income_df, ["营业利润"], report_date_norm)
            da = _extract_value(
                cashflow_df,
                ["固定资产折旧、油气资产折耗、生产性生物资产折旧"],
                report_date_norm,
            )
            if op_income is not None and da is not None:
                fields["ebitda"] = op_income + da
            elif op_income is not None:
                fields["ebitda"] = op_income  # without D&A — still useful

        # book_value_per_share: compute from equity / shares if not directly
        # available from the statement (Sina reports don't include 每股净资产).
        if "book_value_per_share" in line_items and not fields.get("book_value_per_share"):
            equity = _extract_value(
                balance_df,
                ["归属于母公司股东权益合计", "所有者权益(或股东权益)合计"],
                report_date_norm,
            )
            shares = _extract_value(balance_df, ["实收资本(或股本)"], report_date_norm)
            if equity is not None and shares is not None and shares > 0:
                fields["book_value_per_share"] = equity / shares

        # Skip periods where ALL requested fields are None (no data at all).
        if not any(v is not None for v in fields.values()):
            continue
        if not fields:
            continue

        results.append(
            LineItem(
                ticker=ticker,
                report_period=report_period,
                period=period,
                currency="CNY",
                **fields,
            )
        )

    return results


# ---------------------------------------------------------------------------
# 4. Insider trades — STUB
# ---------------------------------------------------------------------------
def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str | None = None,
) -> list[InsiderTrade]:
    """Return ``[]`` for A-shares.

    A-shares have no SEC-equivalent insider-trade public feed exposed via
    akshare. This is an intentional stub.
    """
    return []


# ---------------------------------------------------------------------------
# 5. Company news
# ---------------------------------------------------------------------------
def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str | None = None,
) -> list[CompanyNews]:
    """Fetch news via ``akshare.stock_news_em``.

    Columns: 关键词/新闻标题/新闻内容/发布时间/文章来源/新闻链接.
    ``stock_news_em`` does not support date filtering server-side, so we
    filter client-side and return the latest ``limit`` rows.
    """
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**n) for n in cached_data]

    code = a_share_code(ticker)

    def _fetch() -> pd.DataFrame:
        return ak.stock_news_em(symbol=code)

    try:
        df = _with_retry(_fetch)
    except Exception as e:
        logger.warning("akshare get_company_news failed for %s: %s", ticker, e)
        return []

    if df is None or df.empty:
        return []

    news: list[CompanyNews] = []
    for _, row in df.iterrows():
        try:
            raw_date = str(row.get("发布时间", "")).strip()
            if not raw_date:
                continue
            # 发布时间 looks like "2025-09-15 10:30:00" — normalise to ISO date
            iso_date = raw_date.split(" ")[0] if " " in raw_date else raw_date

            # Apply date window filtering when a start_date is provided
            if start_date and iso_date < start_date:
                continue
            if iso_date > end_date:
                continue

            news.append(
                CompanyNews(
                    ticker=ticker,
                    title=str(row.get("新闻标题", "")).strip() or "(no title)",
                    source=str(row.get("文章来源", "")).strip() or "akshare",
                    date=iso_date,
                    url=str(row.get("新闻链接", "")).strip(),
                    sentiment=None,
                )
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("skipping bad news row for %s: %s", ticker, e)
            continue

    news = news[:limit]
    if not news:
        return []

    _cache.set_company_news(cache_key, [n.model_dump() for n in news])
    return news


# ---------------------------------------------------------------------------
# 6. Market cap
# ---------------------------------------------------------------------------
def _get_spot_table() -> pd.DataFrame | None:
    """Return the shared all-market spot table, fetching it at most once.

    ``stock_zh_a_spot_em`` is the heaviest A-share call (it returns ~5,000
    rows), so concurrent callers must not each fire it. The first miss acquires
    the per-key lock, populates ``_spot_table``, and every subsequent caller —
    including those that waited on the lock — reuses it.
    """
    global _spot_table
    if _spot_table is not None:
        return _spot_table
    with _cache.fetch_lock("akshare:stock_zh_a_spot_em"):
        # Re-check inside the lock: another thread may have populated it while
        # we were queued.
        if _spot_table is not None:
            return _spot_table

        def _fetch_spot() -> pd.DataFrame:
            return ak.stock_zh_a_spot_em()

        # This is the single gating call for every ticker's market cap, so give
        # it real backoff (2s→4s→8s) + jitter — a flat one-shot retry isn't
        # enough if Eastmoney drops the connection under load.
        try:
            df = _with_retry(_fetch_spot, retries=3, delay=2.0, backoff=2.0, jitter=1.0)
        except Exception as e:
            logger.warning("akshare spot-table fetch failed: %s", e)
            return None
        if df is None or df.empty:
            return None
        _spot_table = df
        return _spot_table


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str | None = None,
) -> float | None:
    """Fetch total market cap (CNY) via the shared ``stock_zh_a_spot_em`` table.

    ``stock_zh_a_spot_em`` returns realtime spot data for *all* A-shares
    including a 总市值 column valued in CNY (yuan). Because one call covers
    every ticker, it is fetched once per process (see :func:`_get_spot_table`)
    and shared across the whole analyst fan-out.

    Only returns the live market cap reliably (when ``end_date`` is today or
    near-today). For historical dates the live cap is returned as a proxy (the
    US ``api.py`` does not cache market cap either).

    ``stock_individual_info_em`` (the fallback) is broken in some akshare
    versions — Eastmoney returns a 3-column payload but akshare hardcodes a
    2-column rename → ``ValueError: Length mismatch`` — so it is only used if
    the spot table is unavailable.
    """
    code = a_share_code(ticker)

    # --- Primary: shared all-market spot table (fetched once per process) ---
    spot = _get_spot_table()
    if (
        spot is not None
        and not spot.empty
        and "代码" in spot.columns
        and "总市值" in spot.columns
    ):
        row = spot[spot["代码"] == code]
        if not row.empty:
            cap = _safe_float(row.iloc[0]["总市值"])
            if cap is not None and cap > 0:
                return cap

    # --- Fallback: stock_individual_info_em (broken in some akshare versions) ---
    def _fetch_info() -> pd.DataFrame:
        return ak.stock_individual_info_em(symbol=code)

    try:
        df = _with_retry(_fetch_info)
    except Exception as e:
        logger.warning("akshare get_market_cap failed for %s: %s", ticker, e)
        return None

    if df is None or df.empty:
        return None

    # Normalise defensively: the DataFrame may be 2-col (item, value) or
    # a wider variant. Build a dict[item->value] from the first two columns.
    info: dict[str, object] = {}
    try:
        if len(df.columns) >= 2:
            item_col, value_col = df.columns[0], df.columns[1]
            for _, row in df.iterrows():
                info[str(row[item_col])] = row[value_col]
        else:
            return None
    except (KeyError, TypeError, IndexError):
        return None

    return _safe_float(info.get("总市值"))


# ---------------------------------------------------------------------------
# 7. Re-exported helpers (operate on Price objects, market-agnostic)
# ---------------------------------------------------------------------------
from src.tools.api import prices_to_df, get_price_data  # noqa: E402,F401
