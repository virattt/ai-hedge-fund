"""Financial Modeling Prep (FMP) adapter — used as a fallback when the
Financial Datasets API key isn't set. Requires ``FMP_API_KEY`` (or
``FINANCIAL_MODELING_PREP_API_KEY``) in the environment.

We deliberately only implement the slice needed for the historical
fundamentals backtest: TTM key metrics + ratios at a given report date.
The shape returned mimics ``src.data.models.FinancialMetrics`` closely
enough that ``fundamentals_backtest.historical_fundamentals_at_date``
can consume it interchangeably.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def has_fmp_key() -> bool:
    return bool(os.environ.get("FMP_API_KEY") or os.environ.get("FINANCIAL_MODELING_PREP_API_KEY"))


def _api_key() -> Optional[str]:
    return os.environ.get("FMP_API_KEY") or os.environ.get("FINANCIAL_MODELING_PREP_API_KEY")


def _fetch(url: str, timeout: int = 8):
    req = Request(url, headers={"User-Agent": "strategist/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        import json
        return json.loads(resp.read().decode("utf-8"))


@dataclass
class FMPMetrics:
    report_period: str
    price_to_earnings_ratio: Optional[float] = None
    enterprise_value_to_ebitda_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_invested_capital: Optional[float] = None
    free_cash_flow_yield: Optional[float] = None
    revenue_growth: Optional[float] = None


def fetch_historical_metrics(ticker: str, target_date: str) -> Optional[FMPMetrics]:
    """Return the TTM ratios for the most recent fiscal period <= target_date.

    FMP free tier: `/api/v3/key-metrics-ttm/{ticker}` returns the latest TTM.
    For point-in-time historical, we use `/api/v3/key-metrics/{ticker}?period=quarter&limit=40`
    and pick the most recent fiscalDateEnding <= target_date.
    """
    key = _api_key()
    if not key:
        return None
    try:
        qs = urlencode({"period": "quarter", "limit": 40, "apikey": key})
        url = f"https://financialmodelingprep.com/api/v3/key-metrics/{ticker.upper()}?{qs}"
        rows = _fetch(url)
        if not isinstance(rows, list) or not rows:
            return None
        # Pick the row whose fiscal date is the latest one ≤ target_date
        chosen = None
        for r in rows:
            fde = r.get("date") or r.get("fiscalDateEnding") or ""
            if fde and fde <= target_date:
                if chosen is None or fde > (chosen.get("date") or chosen.get("fiscalDateEnding") or ""):
                    chosen = r
        if chosen is None:
            return None

        # Also pull ratios on same period for growth metrics
        ratios_url = f"https://financialmodelingprep.com/api/v3/ratios/{ticker.upper()}?{qs}"
        try:
            ratio_rows = _fetch(ratios_url)
        except Exception:
            ratio_rows = []
        ratio_match = None
        if isinstance(ratio_rows, list):
            for r in ratio_rows:
                if (r.get("date") or "") == (chosen.get("date") or ""):
                    ratio_match = r
                    break

        return FMPMetrics(
            report_period=chosen.get("date") or chosen.get("fiscalDateEnding") or target_date,
            price_to_earnings_ratio=chosen.get("peRatio"),
            enterprise_value_to_ebitda_ratio=chosen.get("enterpriseValueOverEBITDA"),
            debt_to_equity=chosen.get("debtToEquity"),
            return_on_equity=chosen.get("roe") or (ratio_match.get("returnOnEquity") if ratio_match else None),
            return_on_invested_capital=chosen.get("roic") or (ratio_match.get("returnOnCapitalEmployed") if ratio_match else None),
            free_cash_flow_yield=chosen.get("freeCashFlowYield"),
            revenue_growth=None,  # FMP key-metrics doesn't carry this directly; ratios does sometimes
        )
    except Exception:
        return None
