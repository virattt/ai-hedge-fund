"""Yahoo Finance data client (via yfinance) — free, no API key.

Serves what the pipeline consumes: prices, point-in-time financial metrics,
company facts and earnings history. News and insider trades are not
implemented (nothing in the pipeline reads them).

Coverage limits come from Yahoo's free tier, not from this code:

- Statements cover ~5 quarters and ~4 fiscal years. Metrics rows are TTM sums
  of four consecutive quarters where those exist, plus one row per fiscal year
  (a fiscal year *is* the trailing twelve months at its year end). A live run
  sees ~5-6 rows; a backtest more than about a year back sees fewer, and the
  LLM agents abstain below MIN_PERIODS.
- Yahoo has no SEC filing dates. A period's filing_date is the first earnings
  announcement after its period end — the press release that made the numbers
  public — falling back to a conservative statutory lag when none is known.
- Earnings history comes from Yahoo's earnings calendar (announcement date,
  EPS estimate, reported EPS). Each record is labelled source_type "8-K": it is
  the announcement PEAD's 8-K preference stands in for.
"""

from __future__ import annotations

import bisect
import calendar
import logging
import math
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFEarningsDateMissing, YFPricesMissingError

from hedge_fund.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsData,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
    Price,
)
from hedge_fund.data.sessions import NEW_YORK

logger = logging.getLogger(__name__)

_INTERVALS = {"day": "1d", "week": "1wk", "month": "1mo"}
_ANNOUNCE_WINDOW_DAYS = 120          # an announcement this long after period end is a later one
_FALLBACK_LAG_DAYS = {"quarterly": 45, "annual": 90}  # 10-Q / 10-K deadlines, slowest filers
_EARNINGS_DATES_LIMIT = 40           # ~10 years of quarterly announcements


class YFClientError(Exception):
    """A Yahoo request failed for infrastructure reasons (network, rate
    limit, empty statements for a listed equity). Distinct from "no data
    exists" — that returns empty. A backtest must crash on this."""


class YFinanceClient:
    """DataClient backed by yfinance.

    Usage::

        with YFinanceClient() as yfc:
            prices = yfc.get_prices("AAPL", "2024-01-01", "2024-12-31")
    """

    # CachedDataClient keeps this provider's entries apart from other providers'.
    cache_namespace = "yfinance"

    def __init__(self) -> None:
        self._tickers: dict[str, yf.Ticker] = {}
        self._metrics: dict[str, list[FinancialMetrics]] = {}
        self._announcements: dict[str, list[tuple[pd.Timestamp, float | None, float]]] = {}
        self._closes: dict[str, tuple[list[str], list[float]]] = {}

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> YFinanceClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def close(self) -> None:
        self._tickers.clear()

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "day",
        interval_multiplier: int = 1,
    ) -> list[Price]:
        """OHLCV bars, split-adjusted (not dividend-adjusted), end date inclusive."""
        if interval not in _INTERVALS or interval_multiplier != 1:
            raise ValueError(
                f"yfinance provider supports day/week/month bars with multiplier 1, "
                f"got {interval_multiplier} x {interval}"
            )
        end = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()  # exclusive
        try:
            df = self._ticker(ticker).history(
                start=start_date, end=end, interval=_INTERVALS[interval],
                auto_adjust=False, actions=False, raise_errors=True,
            )
        except YFPricesMissingError:
            return []  # no bars in range (holiday, pre-listing): a data fact
        except Exception as exc:
            raise YFClientError(f"prices {ticker} {start_date}..{end_date}: {exc}") from exc
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        return [
            Price(
                open=float(row.Open), high=float(row.High), low=float(row.Low),
                close=float(row.Close),
                volume=int(row.Volume) if not math.isnan(row.Volume) else 0,
                time=ts.strftime("%Y-%m-%d"),
            )
            for ts, row in df.iterrows()
        ]

    # ------------------------------------------------------------------
    # Financial metrics
    # ------------------------------------------------------------------

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[FinancialMetrics]:
        """Metrics rows public by *end_date* (filing_date <= end_date), newest first.

        ``ttm`` mixes quarterly-TTM and fiscal-year rows; ``annual`` keeps
        only the fiscal-year rows.
        """
        if period not in ("ttm", "annual"):
            raise ValueError(f"yfinance provider supports period ttm/annual, got {period!r}")
        rows = self._all_metrics(ticker)
        if period == "annual":
            rows = [r for r in rows if r.period == "annual"]
        return [r for r in rows if r.filing_date and r.filing_date <= end_date][:limit]

    def _all_metrics(self, ticker: str) -> list[FinancialMetrics]:
        if ticker not in self._metrics:
            self._metrics[ticker] = self._build_metrics(ticker)
        return self._metrics[ticker]

    def _build_metrics(self, ticker: str) -> list[FinancialMetrics]:
        t = self._ticker(ticker)
        try:
            qi, qb, qc = t.quarterly_income_stmt, t.quarterly_balance_sheet, t.quarterly_cashflow
            ai, ab, ac = t.income_stmt, t.balance_sheet, t.cashflow
        except Exception as exc:
            raise YFClientError(f"statements {ticker}: {exc}") from exc
        if qi.empty and ai.empty:
            # ETFs and indices have no statements. A listed equity always
            # does, so empty there means Yahoo failed quietly — fail loud.
            if self._info(ticker).get("quoteType") == "EQUITY":
                raise YFClientError(f"statements {ticker}: Yahoo returned no data")
            return []

        # report_period -> (kind, flows). Fiscal-year rows win over a TTM row
        # for the same period end: same twelve months, audited figures.
        periods: dict[pd.Timestamp, tuple[str, dict]] = {}
        for end in _live_columns(ai):
            periods[end] = ("annual", _flows(ai, ac, [end]))
        q_cols = _live_columns(qi)
        for i in range(3, len(q_cols)):
            window = q_cols[i - 3:i + 1]
            if _consecutive_quarters(window):
                periods.setdefault(window[-1], ("quarterly", _flows(qi, qc, window)))
        if not periods:
            return []

        flows_by_end = {end: flows for end, (_, flows) in periods.items()}
        rows = []
        for end, (kind, flows) in periods.items():
            # Market cap at the filing date's close: what the market priced
            # the company at the moment these numbers became public.
            filed = self._filing_date(ticker, end, kind)
            price = self._close_on_or_before(ticker, filed, min(periods))
            growth = {
                "revenue_growth": _yoy(flows_by_end, end, kind, "revenue", qi, "Total Revenue"),
                "earnings_growth": _yoy(flows_by_end, end, kind, "net_income", qi, "Net Income"),
            }
            rows.append(_metrics_row(ticker, end, kind, flows, _balance(qb, ab, end),
                                     filed, price, growth))
        return sorted(rows, key=lambda r: r.report_period, reverse=True)

    def _filing_date(self, ticker: str, period_end: pd.Timestamp, kind: str) -> str:
        """First earnings announcement after *period_end*, else a statutory lag."""
        end = period_end.date()
        for ts, _, _ in reversed(self._earnings_dates(ticker)):  # oldest first
            day = ts.date()
            if end < day <= end + timedelta(days=_ANNOUNCE_WINDOW_DAYS):
                return day.isoformat()
        return (end + timedelta(days=_FALLBACK_LAG_DAYS[kind])).isoformat()

    def _close_on_or_before(self, ticker: str, day: str, since: pd.Timestamp) -> float | None:
        if ticker not in self._closes:
            bars = self.get_prices(ticker, since.date().isoformat(), date.today().isoformat())
            self._closes[ticker] = ([b.time for b in bars], [b.close for b in bars])
        days, closes = self._closes[ticker]
        i = bisect.bisect_right(days, day)
        return closes[i - 1] if i else None

    # ------------------------------------------------------------------
    # Company facts
    # ------------------------------------------------------------------

    def get_company_facts(self, ticker: str) -> CompanyFacts | None:
        info = self._info(ticker)
        name = info.get("longName") or info.get("shortName")
        if not name:
            return None  # Yahoo answers unknown symbols with a near-empty dict
        return CompanyFacts(
            ticker=ticker,
            name=name,
            sector=info.get("sector"),
            industry=info.get("industry"),
            category=info.get("quoteType"),
            exchange=info.get("exchange"),
            location=", ".join(p for p in (info.get("city"), info.get("country")) if p) or None,
        )

    # ------------------------------------------------------------------
    # Earnings
    # ------------------------------------------------------------------

    def get_earnings(self, ticker: str) -> Earnings | None:
        history = self.get_earnings_history(ticker, limit=1)
        if not history:
            return None
        r = history[0]
        return Earnings(ticker=ticker, report_period=r.report_period, quarterly=r.quarterly)

    def get_earnings_history(self, ticker: str, limit: int = 12) -> list[EarningsRecord]:
        """Reported earnings announcements, newest first.

        report_period is the fiscal quarter end the announcement covers: the
        last quarter-end month before the announcement, on the fiscal
        calendar read off the quarterly statements (calendar quarters if
        there are none).
        """
        offset = self._fiscal_quarter_offset(ticker)
        records = []
        for ts, estimate, reported in self._earnings_dates(ticker)[:limit]:
            day = ts.date()
            records.append(EarningsRecord(
                ticker=ticker,
                report_period=_quarter_end_before(day, offset).isoformat(),
                source_type="8-K",
                filing_date=day.isoformat(),
                filing_datetime=ts.isoformat(),
                quarterly=EarningsData(
                    earnings_per_share=reported,
                    estimated_earnings_per_share=estimate,
                    eps_surprise=_surprise(reported, estimate),
                ),
            ))
        return records

    def _earnings_dates(self, ticker: str) -> list[tuple[pd.Timestamp, float | None, float]]:
        """(announcement time in New York, EPS estimate, reported EPS), newest
        first, reported announcements only (upcoming ones have no EPS yet)."""
        if ticker not in self._announcements:
            try:
                df = self._ticker(ticker).get_earnings_dates(limit=_EARNINGS_DATES_LIMIT)
            except YFEarningsDateMissing:
                df = None  # ETFs and the like have no earnings calendar
            except Exception as exc:
                raise YFClientError(f"earnings dates {ticker}: {exc}") from exc
            rows = []
            if df is not None and not df.empty:
                for ts, row in df.iterrows():
                    reported = _num(row.get("Reported EPS"))
                    if reported is None:
                        continue
                    rows.append((ts.tz_convert(NEW_YORK), _num(row.get("EPS Estimate")), reported))
            self._announcements[ticker] = sorted(rows, key=lambda r: r[0], reverse=True)
        return self._announcements[ticker]

    def _fiscal_quarter_offset(self, ticker: str) -> int:
        """Month-of-quarter (0..2, via month % 3) on which fiscal quarters end."""
        try:
            cols = _live_columns(self._ticker(ticker).quarterly_income_stmt)
        except Exception as exc:
            raise YFClientError(f"statements {ticker}: {exc}") from exc
        return cols[-1].month % 3 if cols else 0

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        """Shares outstanding x close, as of the latest filing public by *end_date*."""
        metrics = self.get_financial_metrics(ticker, end_date, limit=1)
        return metrics[0].market_cap if metrics else None

    def get_news(self, ticker, end_date, start_date=None, limit=1000) -> list[CompanyNews]:
        raise NotImplementedError(
            "news is not available from the yfinance provider; "
            "set HEDGE_FUND_DATA_SOURCE=financialdatasets"
        )

    def get_insider_trades(self, ticker, end_date, start_date=None, limit=1000) -> list[InsiderTrade]:
        raise NotImplementedError(
            "insider trades are not available from the yfinance provider; "
            "set HEDGE_FUND_DATA_SOURCE=financialdatasets"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ticker(self, ticker: str) -> yf.Ticker:
        # One Ticker per symbol: yfinance memoizes statements on the object.
        if ticker not in self._tickers:
            self._tickers[ticker] = yf.Ticker(ticker)
        return self._tickers[ticker]

    def _info(self, ticker: str) -> dict:
        try:
            return self._ticker(ticker).info or {}
        except Exception as exc:
            raise YFClientError(f"info {ticker}: {exc}") from exc


# ---------------------------------------------------------------------------
# Statement arithmetic (pure functions over yfinance DataFrames)
# ---------------------------------------------------------------------------

def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _cell(df: pd.DataFrame, rows: tuple[str, ...], col) -> float | None:
    """First non-null value among *rows* (label fallbacks) in column *col*."""
    if df is None or df.empty or col not in df.columns:
        return None
    for row in rows:
        if row in df.index:
            v = _num(df.at[row, col])
            if v is not None:
                return v
    return None


def _live_columns(df: pd.DataFrame) -> list[pd.Timestamp]:
    """Period-end columns that carry data, oldest first. Yahoo pads the oldest
    column with NaNs; a column without revenue or net income is no period."""
    if df is None or df.empty:
        return []
    return sorted(
        col for col in df.columns
        if _cell(df, ("Total Revenue",), col) is not None
        or _cell(df, ("Net Income",), col) is not None
    )


def _consecutive_quarters(cols: list[pd.Timestamp]) -> bool:
    return all(80 <= (b - a).days <= 100 for a, b in zip(cols, cols[1:]))


_FLOW_ROWS = {
    "revenue": ("Total Revenue",),
    "gross_profit": ("Gross Profit",),
    "operating_income": ("Operating Income",),
    "net_income": ("Net Income", "Net Income Common Stockholders"),
    "eps": ("Diluted EPS", "Basic EPS"),
}


def _flows(income: pd.DataFrame, cashflow: pd.DataFrame, cols: list) -> dict:
    """Sum flow items over *cols* (one fiscal year, or four quarters).
    An item missing in any column is None — a partial sum is a wrong number."""
    def total(df, rows):
        values = [_cell(df, rows, c) for c in cols]
        return sum(values) if all(v is not None for v in values) else None

    flows = {key: total(income, rows) for key, rows in _FLOW_ROWS.items()}
    fcf = total(cashflow, ("Free Cash Flow",))
    if fcf is None:
        ocf = total(cashflow, ("Operating Cash Flow",))
        capex = total(cashflow, ("Capital Expenditure",))  # negative on Yahoo
        fcf = ocf + capex if ocf is not None and capex is not None else None
    flows["fcf"] = fcf
    return flows


def _balance(quarterly: pd.DataFrame, annual: pd.DataFrame, end) -> dict:
    """Balance-sheet items at *end* (quarterly sheet first, then annual)."""
    def get(rows):
        v = _cell(quarterly, rows, end)
        return v if v is not None else _cell(annual, rows, end)

    return {
        "equity": get(("Stockholders Equity", "Common Stock Equity")),
        "total_debt": get(("Total Debt",)),
        "total_assets": get(("Total Assets",)),
        "current_assets": get(("Current Assets",)),
        "current_liabilities": get(("Current Liabilities",)),
        "shares": get(("Ordinary Shares Number", "Share Issued")),
    }


def _ratio(a: float | None, b: float | None, positive_denominator: bool = False) -> float | None:
    if a is None or b is None or b == 0 or (positive_denominator and b < 0):
        return None
    return round(a / b, 4)


def _quarter_end_before(day: date, offset: int) -> date:
    """Last month end strictly before *day* whose month % 3 == *offset*."""
    year, month = day.year, day.month
    while True:
        end = date(year, month, calendar.monthrange(year, month)[1])
        if end < day and month % 3 == offset:
            return end
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)


def _surprise(reported: float, estimate: float | None) -> str | None:
    if estimate is None:
        return None
    diff = round(reported - estimate, 4)
    return "BEAT" if diff > 0 else "MISS" if diff < 0 else "MEET"


def _growth(now: float | None, before: float | None) -> float | None:
    if now is None or before is None or before <= 0:
        return None
    return round(now / before - 1, 4)


def _yoy(flows_by_end: dict, end, kind: str, key: str,
         quarterly_income: pd.DataFrame, label: str) -> float | None:
    """Growth vs. the twelve months a year earlier. A quarterly-TTM row with
    no year-ago row (Yahoo's ~5 quarters rarely reach) falls back to its
    latest quarter vs. the same quarter a year earlier."""
    for other, flows in flows_by_end.items():
        if 345 <= (end - other).days <= 385:
            return _growth(flows_by_end[end][key], flows[key])
    if kind == "quarterly":
        for col in _live_columns(quarterly_income):
            if 345 <= (end - col).days <= 385:
                return _growth(_cell(quarterly_income, (label,), end),
                               _cell(quarterly_income, (label,), col))
    return None


def _metrics_row(ticker, end, kind, flows, bal, filed, price, growth) -> FinancialMetrics:
    revenue, ni, eps, fcf = flows["revenue"], flows["net_income"], flows["eps"], flows["fcf"]
    equity, shares = bal["equity"], bal["shares"]
    market_cap = shares * price if shares is not None and price is not None else None
    return FinancialMetrics(
        ticker=ticker,
        report_period=end.date().isoformat(),
        period=kind,
        filing_date=filed,
        market_cap=market_cap,
        **growth,
        price_to_earnings_ratio=_ratio(price, eps) if eps is not None and eps > 0 else None,
        price_to_book_ratio=_ratio(market_cap, equity, positive_denominator=True),
        price_to_sales_ratio=_ratio(market_cap, revenue, positive_denominator=True),
        free_cash_flow_yield=_ratio(fcf, market_cap, positive_denominator=True),
        gross_margin=_ratio(flows["gross_profit"], revenue),
        operating_margin=_ratio(flows["operating_income"], revenue),
        net_margin=_ratio(ni, revenue),
        return_on_equity=_ratio(ni, equity, positive_denominator=True),
        return_on_assets=_ratio(ni, bal["total_assets"], positive_denominator=True),
        current_ratio=_ratio(bal["current_assets"], bal["current_liabilities"]),
        debt_to_equity=_ratio(bal["total_debt"], equity, positive_denominator=True),
        debt_to_assets=_ratio(bal["total_debt"], bal["total_assets"]),
        earnings_per_share=round(eps, 4) if eps is not None else None,
        book_value_per_share=_ratio(equity, shares),
        free_cash_flow_per_share=_ratio(fcf, shares),
    )
