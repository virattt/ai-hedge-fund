"""Historical FUNDAMENTAL backtest via Financial Datasets API.

`src/analysis/backtest.py` runs technicals at any past date. This module
extends that to fundamentals: it pulls the point-in-time TTM financial
metrics from Financial Datasets (`get_financial_metrics`), feeds them
through the same verdict rules used in the live snapshot, and produces
a combined verdict for the historical date.

Requires `FINANCIAL_DATASETS_API_KEY` in the environment. If missing,
`historical_fundamentals_at_date()` returns None and the UI degrades
gracefully (technical-only backtest stays available).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.analysis.verdicts import (
    MetricRow,
    Verdict,
    aggregate_verdict,
    verdict_debt_equity,
    verdict_ev_ebitda,
    verdict_fcf_yield,
    verdict_pe,
    verdict_revenue_growth,
    verdict_roe,
    verdict_roic,
)


@dataclass
class HistoricalFundamentalsPoint:
    as_of_date: str
    label: str                                 # "1Y ago", "6M ago" etc.
    report_period: str                         # actual period the API returned
    metrics: list[MetricRow] = field(default_factory=list)
    fundamental_verdict: Verdict = "N/A"
    fundamental_confidence: float = 0.0
    price_then: Optional[float] = None
    price_now: Optional[float] = None
    realized_return: Optional[float] = None
    correct: Optional[bool] = None
    error: Optional[str] = None


def _has_api_key() -> bool:
    return bool(os.environ.get("FINANCIAL_DATASETS_API_KEY"))


def historical_fundamentals_at_date(
    ticker: str,
    target_date: str,
    close: pd.Series,
) -> Optional[HistoricalFundamentalsPoint]:
    """Pull point-in-time financial metrics and grade them.

    Returns None if the API key isn't set or the call returns no data.
    """
    if not _has_api_key():
        return HistoricalFundamentalsPoint(
            as_of_date=target_date,
            label="—",
            report_period="—",
            error="FINANCIAL_DATASETS_API_KEY not set — historical fundamentals unavailable. Free fallback uses technical signals only.",
        )

    try:
        from src.tools.api import get_financial_metrics
        metrics_list = get_financial_metrics(
            ticker=ticker.upper(),
            end_date=target_date,
            period="ttm",
            limit=1,
        )
    except Exception as exc:
        return HistoricalFundamentalsPoint(
            as_of_date=target_date,
            label="—",
            report_period="—",
            error=f"financial_datasets call failed: {exc}",
        )

    if not metrics_list:
        return HistoricalFundamentalsPoint(
            as_of_date=target_date,
            label="—",
            report_period="—",
            error="no financial metrics returned for that date",
        )

    fm = metrics_list[0]  # most-recent TTM metrics with report_period <= target_date

    # Grade each available metric using the same rules as the live snapshot
    rows: list[MetricRow] = []

    def _row(name: str, value, unit: str, fn) -> MetricRow:
        verdict, rationale = fn(value)
        return MetricRow(name=name, value=value, unit=unit, verdict=verdict, rationale=rationale)

    rows.append(_row("P/E (TTM)", fm.price_to_earnings_ratio, "x", verdict_pe))
    rows.append(_row("EV/EBITDA", fm.enterprise_value_to_ebitda_ratio, "x", verdict_ev_ebitda))
    rows.append(_row("Debt / Equity", fm.debt_to_equity, "x", verdict_debt_equity))
    rows.append(_row("ROE", fm.return_on_equity, "%", verdict_roe))
    rows.append(_row("ROIC", fm.return_on_invested_capital, "%", verdict_roic))
    rows.append(_row("FCF Yield", fm.free_cash_flow_yield, "%", verdict_fcf_yield))
    rows.append(_row("Revenue Growth", fm.revenue_growth, "%", verdict_revenue_growth))

    verdict, conf = aggregate_verdict(rows)

    # Realized return from price series
    price_then = None
    price_now = None
    realized = None
    correct = None
    if isinstance(close.index, pd.DatetimeIndex) and len(close):
        target_ts = pd.Timestamp(target_date)
        if close.index.tz is not None and target_ts.tz is None:
            target_ts = target_ts.tz_localize(close.index.tz)
        valid = close.index[close.index <= target_ts]
        if len(valid) > 0:
            idx = close.index.get_loc(valid[-1])
            try:
                price_then = float(close.iloc[idx])
                price_now = float(close.iloc[-1])
                realized = price_now / price_then - 1.0
                if verdict in ("BUY", "STRONG BUY"):
                    correct = realized > 0
                elif verdict in ("SELL", "REDUCE"):
                    correct = realized < 0
                elif verdict == "HOLD":
                    correct = abs(realized) < 0.15
            except Exception:
                pass

    # Build label from time gap
    label = "—"
    if price_then is not None:
        try:
            days_back = (close.index[-1] - close.index[close.index.get_loc(valid[-1])]).days
            months = days_back / 30
            label = f"{months:.1f}M ago"
        except Exception:
            pass

    return HistoricalFundamentalsPoint(
        as_of_date=target_date,
        label=label,
        report_period=fm.report_period,
        metrics=rows,
        fundamental_verdict=verdict,
        fundamental_confidence=conf,
        price_then=price_then,
        price_now=price_now,
        realized_return=realized,
        correct=correct,
    )
