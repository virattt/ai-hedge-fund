"""Finnhub data client — fundamentals, earnings, insider trades, company facts."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import requests

from integrations.data.config import DataConfig
from integrations.data.errors import DataClientError
from integrations.data.line_items import extract_line_item
from v2.data.models import (
    CompanyFacts,
    Earnings,
    EarningsData,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://finnhub.io/api/v1"
_RETRY_DELAYS = (2, 5, 10)


class FinnhubDataClient:
    """Fetch fundamentals and corporate data from Finnhub."""

    def __init__(self, config: DataConfig) -> None:
        self._api_key = config.finnhub_api_key
        self._session = requests.Session()

    def close(self) -> None:
        self._session.close()

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        params = dict(params or {})
        params["token"] = self._api_key
        url = f"{_BASE_URL}{path}"

        for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
            try:
                resp = self._session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                raise DataClientError(f"Finnhub {path} failed: {exc}", path=path) from exc

            if resp.status_code == 429 and delay is not None:
                time.sleep(delay)
                continue

            if resp.status_code == 404:
                return {}

            if resp.status_code >= 400:
                raise DataClientError(
                    f"Finnhub {path} returned {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                    path=path,
                )

            return resp.json()

        raise DataClientError(f"Finnhub {path} rate limited after retries", status_code=429, path=path)

    def _get_profile(self, ticker: str) -> dict:
        data = self._get("/stock/profile2", {"symbol": ticker.upper()})
        return data if isinstance(data, dict) else {}

    def get_company_facts(self, ticker: str) -> CompanyFacts | None:
        data = self._get_profile(ticker)
        if not data:
            return None
        return CompanyFacts(
            ticker=ticker.upper(),
            name=data.get("name"),
            industry=data.get("finnhubIndustry"),
            sector=data.get("finnhubIndustry"),
            exchange=data.get("exchange"),
            is_active=data.get("marketCapitalization") is not None,
        )

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        # Finnhub reports marketCapitalization in millions.
        profile = self._get_profile(ticker)
        raw_cap = profile.get("marketCapitalization")
        if raw_cap:
            return float(raw_cap) * 1_000_000
        metrics = self.get_financial_metrics(ticker, end_date, limit=1)
        if metrics and metrics[0].market_cap:
            return metrics[0].market_cap
        return None

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[FinancialMetrics]:
        freq = "annual" if period == "annual" else "quarterly"
        reported = self._get(
            "/stock/financials-reported",
            {"symbol": ticker.upper(), "freq": freq},
        )
        filings = reported.get("data", []) if isinstance(reported, dict) else []

        end = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
        metrics_data = self._get("/stock/metric", {"symbol": ticker.upper(), "metric": "all"})
        current = metrics_data.get("metric", {}) if isinstance(metrics_data, dict) else {}

        results: list[FinancialMetrics] = []
        for filing in filings:
            filing_date_str = (filing.get("filingDate") or filing.get("acceptedDate", ""))[:10]
            if not filing_date_str:
                continue
            filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
            if filing_date > end:
                continue

            report_period = (filing.get("period") or filing_date_str)[:10]
            report = filing.get("report", {})

            results.append(
                FinancialMetrics(
                    ticker=ticker.upper(),
                    report_period=report_period,
                    period=period,
                    currency="USD",
                    filing_date=filing_date_str,
                    market_cap=_millions(current.get("marketCapitalization")),
                    price_to_earnings_ratio=_safe_float(current.get("peTTM")),
                    price_to_book_ratio=_safe_float(current.get("pbQuarterly")),
                    price_to_sales_ratio=_safe_float(current.get("psTTM")),
                    peg_ratio=_safe_float(current.get("pegTTM")),
                    gross_margin=_ratio(current.get("grossMarginTTM")),
                    operating_margin=_ratio(current.get("operatingMarginTTM")),
                    net_margin=_ratio(current.get("netProfitMarginTTM")),
                    return_on_equity=_ratio(current.get("roeTTM")),
                    return_on_assets=_ratio(current.get("roaTTM")),
                    return_on_invested_capital=_ratio(current.get("roiTTM")),
                    current_ratio=_safe_float(current.get("currentRatioQuarterly")),
                    debt_to_equity=_safe_float(current.get("totalDebt/totalEquityQuarterly")),
                    revenue_growth=_ratio(current.get("revenueGrowthTTMYoy")),
                    earnings_growth=_ratio(current.get("epsGrowthTTMYoy")),
                    earnings_per_share=_safe_float(current.get("epsTTM")),
                    free_cash_flow_per_share=_safe_float(current.get("freeCashFlowPerShareTTM")),
                )
            )

        results.sort(key=lambda m: m.report_period, reverse=True)
        return results[:limit]

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[dict]:
        freq = "annual" if period == "annual" else "quarterly"
        reported = self._get(
            "/stock/financials-reported",
            {"symbol": ticker.upper(), "freq": freq},
        )
        filings = reported.get("data", []) if isinstance(reported, dict) else []
        end = datetime.strptime(end_date[:10], "%Y-%m-%d").date()

        rows: list[dict] = []
        for filing in filings:
            filing_date_str = (filing.get("filingDate") or filing.get("acceptedDate", ""))[:10]
            if not filing_date_str:
                continue
            if datetime.strptime(filing_date_str, "%Y-%m-%d").date() > end:
                continue

            report_period = (filing.get("period") or filing_date_str)[:10]
            report = filing.get("report", {})
            row: dict = {
                "ticker": ticker.upper(),
                "report_period": report_period,
                "period": period,
                "currency": "USD",
            }
            # Always set every requested line item (None if unavailable) so
            # agents that access item.<field> never hit AttributeError.
            for item in line_items:
                row[item] = extract_line_item(report, item)

            _fill_derived_line_items(row, report)
            rows.append(row)

        rows.sort(key=lambda r: r["report_period"], reverse=True)
        return rows[:limit]

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]:
        start = start_date or (datetime.strptime(end_date[:10], "%Y-%m-%d") - timedelta(days=365)).strftime(
            "%Y-%m-%d"
        )
        data = self._get(
            "/stock/insider-transactions",
            {"symbol": ticker.upper(), "from": start, "to": end_date[:10]},
        )
        trades = data.get("data", []) if isinstance(data, dict) else []

        results: list[InsiderTrade] = []
        for trade in trades[:limit]:
            filing_date = (trade.get("filingDate") or trade.get("transactionDate") or end_date)[:10]
            results.append(
                InsiderTrade(
                    ticker=ticker.upper(),
                    name=trade.get("name"),
                    filing_date=filing_date,
                    transaction_date=trade.get("transactionDate"),
                    transaction_shares=trade.get("share"),
                    transaction_price_per_share=trade.get("transactionPrice"),
                    transaction_value=(
                        float(trade["share"]) * float(trade["transactionPrice"])
                        if trade.get("share") and trade.get("transactionPrice")
                        else None
                    ),
                )
            )
        return results

    def get_earnings(self, ticker: str) -> Earnings | None:
        history = self.get_earnings_history(ticker, limit=1)
        if not history:
            return None
        record = history[0]
        return Earnings(
            ticker=record.ticker,
            report_period=record.report_period,
            quarterly=record.quarterly,
            annual=record.annual,
        )

    def get_earnings_history(self, ticker: str, limit: int = 12) -> list[EarningsRecord]:
        earnings = self._get("/stock/earnings", {"symbol": ticker.upper()})
        if not isinstance(earnings, list):
            return []

        calendar = self._earnings_calendar_map(ticker)
        results: list[EarningsRecord] = []
        for row in earnings[: limit * 2]:
            period = row.get("period")
            if not period:
                continue
            actual = row.get("actual")
            estimate = row.get("estimate")
            surprise = _eps_surprise(actual, estimate)
            year = row.get("year")
            quarter = row.get("quarter")
            filing_date = calendar.get((year, quarter), period)

            results.append(
                EarningsRecord(
                    ticker=ticker.upper(),
                    report_period=period[:10],
                    source_type="8-K",
                    filing_date=filing_date[:10],
                    quarterly=EarningsData(
                        earnings_per_share=actual,
                        estimated_earnings_per_share=estimate,
                        eps_surprise=surprise,
                    ),
                )
            )

        results.sort(key=lambda r: r.filing_date or r.report_period, reverse=True)
        return results[:limit]

    def _earnings_calendar_map(self, ticker: str) -> dict[tuple, str]:
        """Map (year, quarter) -> announcement date from earnings calendar."""
        from_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        data = self._get(
            "/calendar/earnings",
            {"symbol": ticker.upper(), "from": from_date, "to": to_date},
        )
        calendar_rows = data.get("earningsCalendar", []) if isinstance(data, dict) else []
        mapping: dict[tuple, str] = {}
        for row in calendar_rows:
            year = row.get("year")
            quarter = row.get("quarter")
            date = row.get("date")
            if year is not None and quarter is not None and date:
                mapping[(year, quarter)] = date[:10]
        return mapping


def _fill_derived_line_items(row: dict, report: dict) -> None:
    """Compute ratio/derived line items that have no direct XBRL concept.

    Only fills keys the caller requested (already present in *row*) and only
    when the value is still None. Uses raw concepts from *report*.
    """
    from integrations.data.line_items import extract_line_item

    def base(name: str):
        if name in row and row[name] is not None:
            return row[name]
        return extract_line_item(report, name)

    revenue = base("revenue")
    operating_income = base("operating_income")
    gross_profit = base("gross_profit")
    total_debt = base("total_debt")
    equity = base("shareholders_equity")
    shares = base("outstanding_shares")
    current_assets = base("current_assets")
    current_liabilities = base("current_liabilities")
    dep_amort = base("depreciation_and_amortization")

    derived: dict[str, float | None] = {}
    if revenue:
        if operating_income is not None:
            derived["operating_margin"] = operating_income / revenue
        if gross_profit is not None:
            derived["gross_margin"] = gross_profit / revenue
    if equity:
        if total_debt is not None:
            derived["debt_to_equity"] = total_debt / equity
        if shares:
            derived["book_value_per_share"] = equity / shares
    if operating_income is not None and dep_amort is not None:
        derived["ebitda"] = operating_income + dep_amort
    if current_assets is not None and current_liabilities is not None:
        derived["working_capital"] = current_assets - current_liabilities

    for key, value in derived.items():
        if key in row and row[key] is None:
            row[key] = value


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _millions(value) -> float | None:
    v = _safe_float(value)
    return v * 1_000_000 if v is not None else None


def _ratio(value) -> float | None:
    v = _safe_float(value)
    if v is None:
        return None
    if abs(v) > 1:
        return v / 100.0
    return v


def _eps_surprise(actual, estimate) -> str | None:
    if actual is None or estimate is None:
        return None
    actual_f = float(actual)
    estimate_f = float(estimate)
    if actual_f > estimate_f:
        return "BEAT"
    if actual_f < estimate_f:
        return "MISS"
    return "MEET"
