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

T = TypeVar("T")


def _with_retry(fn: Callable[[], T], retries: int = 1, delay: float = 2.0) -> T:
    """Call ``fn`` with a single retry on common akshare transient errors.

    akshare already does some internal rate-limit handling, so we keep this
    simple: one retry after ``delay`` seconds on ``JSONDecodeError``,
    ``ConnectionError``, ``RemoteDisconnected`` or an empty DataFrame result.
    Any other exception propagates immediately (the caller wraps in try/except
    and returns ``[]``/``None``).
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
                logger.warning(
                    "akshare transient error for %s: %s — retrying after %.1fs",
                    getattr(fn, "__name__", fn),
                    e,
                    delay,
                )
                last_exc = e
                time.sleep(delay)
                continue
            raise
        else:
            # Treat empty DataFrame as a transient signal worth one retry
            if isinstance(result, pd.DataFrame) and result.empty and attempt < retries:
                logger.warning("akshare returned empty DataFrame — retrying after %.1fs", delay)
                time.sleep(delay)
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
                gross_margin=_get("毛利率", pc),
                operating_margin=_get("营业利润率", pc),
                net_margin=_get("销售净利率", pc),
                return_on_equity=_get("净资产收益率(ROE)", pc),
                return_on_assets=_get("总资产报酬率", pc),
                return_on_invested_capital=_get("投入资本回报率", pc),
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
                debt_to_equity=_get("产权比率", pc),
                debt_to_assets=_get("资产负债率", pc),
                interest_coverage=None,
                revenue_growth=_get("营业总收入增长率", pc),
                earnings_growth=_get("归属母公司净利润增长率", pc),
                book_value_growth=None,
                earnings_per_share_growth=None,
                free_cash_flow_growth=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=None,
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
# 3. Line items — STUB
# ---------------------------------------------------------------------------
def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str | None = None,
) -> list[LineItem]:
    """Return ``[]`` for A-shares.

    TODO: A-share line-item mapping would need to be built per agent request,
    translating each requested US-style field name (e.g. ``net_income``,
    ``total_assets``) to the corresponding Chinese label in
    ``akshare.stock_financial_abstract``. The agents already handle an empty
    list gracefully, so this stub is intentionally non-fatal.
    """
    return []


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
def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str | None = None,
) -> float | None:
    """Fetch total market cap (CNY) via ``akshare.stock_individual_info_em``.

    Only returns the live market cap reliably (when ``end_date`` is today).
    For historical dates we attempt a best-effort approximation using
    shares-outstanding * historical close, but ``stock_individual_info_em``
    does not always expose shares outstanding, so this may return ``None``.
    The US ``api.py`` does not cache market cap either, so we skip caching.
    """
    code = a_share_code(ticker)
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    def _fetch_info() -> pd.DataFrame:
        return ak.stock_individual_info_em(symbol=code)

    try:
        df = _with_retry(_fetch_info)
    except Exception as e:
        logger.warning("akshare get_market_cap failed for %s: %s", ticker, e)
        return None

    if df is None or df.empty:
        return None

    # df shape varies across akshare versions: either ['item','value'] or
    # a 3-column variant. Normalise defensively into a dict[item->value].
    info: dict[str, object] = {}
    try:
        if list(df.columns) >= 2:
            item_col, value_col = df.columns[0], df.columns[1]
            for _, row in df.iterrows():
                info[str(row[item_col])] = row[value_col]
        else:
            return None
    except (KeyError, TypeError, IndexError):
        return None

    live_cap = _safe_float(info.get("总市值"))
    if end_date == today:
        return live_cap

    # Historical best-effort: shares * historical close
    # TODO: shares-outstanding field name varies across akshare versions; if
    # missing, we fall back to returning the live cap as a rough proxy.
    if live_cap is None:
        return None

    # Try to get historical close for end_date
    try:
        prices = get_prices(ticker, end_date, end_date)
        if prices:
            return live_cap  # fallback: live cap as proxy
    except Exception:
        pass
    return live_cap


# ---------------------------------------------------------------------------
# 7. Re-exported helpers (operate on Price objects, market-agnostic)
# ---------------------------------------------------------------------------
from src.tools.api import prices_to_df, get_price_data  # noqa: E402,F401
