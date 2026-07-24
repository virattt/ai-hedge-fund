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


def _has_financial_datasets_key() -> bool:
    return bool(os.environ.get("FINANCIAL_DATASETS_API_KEY"))


def _fetch_metrics_any_source(ticker: str, target_date: str):
    """Try Financial Datasets first, then FMP. Returns an object with
    attributes matching the fields we render (.report_period, .price_to_earnings_ratio,
    .enterprise_value_to_ebitda_ratio, .debt_to_equity, .return_on_equity,
    .return_on_invested_capital, .free_cash_flow_yield, .revenue_growth) or
    None if no source is configured / no data found.
    """
    # Source 1: Financial Datasets (preferred — gives revenue_growth + ROIC)
    if _has_financial_datasets_key():
        try:
            from src.tools.api import get_financial_metrics
            metrics_list = get_financial_metrics(
                ticker=ticker.upper(),
                end_date=target_date,
                period="ttm",
                limit=1,
            )
            if metrics_list:
                return metrics_list[0], "Financial Datasets"
        except Exception:
            pass

    # Source 2: Financial Modeling Prep
    from src.analysis.fmp_adapter import fetch_historical_metrics, has_fmp_key
    if has_fmp_key():
        fmp = fetch_historical_metrics(ticker, target_date)
        if fmp:
            return fmp, "Financial Modeling Prep"

    return None, None


def historical_fundamentals_at_date(
    ticker: str,
    target_date: str,
    close: pd.Series,
) -> Optional[HistoricalFundamentalsPoint]:
    """Pull point-in-time financial metrics and grade them.

    Tries Financial Datasets first, then FMP. Returns a result object with
    `.error` populated if no source is configured.
    """
    fm, source = _fetch_metrics_any_source(ticker, target_date)
    if fm is None:
        return HistoricalFundamentalsPoint(
            as_of_date=target_date,
            label="—",
            report_period="—",
            error=(
                "No fundamentals API key configured. Set FINANCIAL_DATASETS_API_KEY "
                "or FMP_API_KEY in .env to enable historical fundamental verdicts. "
                "Technical-only backtest still works."
            ),
        )

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
