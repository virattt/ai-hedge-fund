"""Data quality and coverage factors.

A stock our pipeline cannot see clearly is a stock it cannot trade well:
gaps in bars, missing fundamentals, and stale filings all degrade every
downstream signal.
"""

from __future__ import annotations

import math
from datetime import datetime

import pandas as pd

from integrations.universe.factors.base import Factor, FactorContext

_WINDOW = 252

# FinancialMetrics fields that the rule-based analysts actually consume.
_KEY_FUNDAMENTAL_FIELDS = (
    "market_cap",
    "price_to_earnings_ratio",
    "price_to_book_ratio",
    "return_on_equity",
    "net_margin",
    "operating_margin",
    "revenue_growth",
    "earnings_growth",
    "debt_to_equity",
    "current_ratio",
    "free_cash_flow_per_share",
    "earnings_per_share",
)


class BarCoverageFactor(Factor):
    """Fraction of the trailing year's calendar-weekdays with a bar."""

    name = "bar_coverage"

    def compute(self, ctx: FactorContext) -> float | None:
        bars = ctx.prices.tail(_WINDOW)
        if len(bars) < 2:
            return None
        span_weekdays = len(pd.bdate_range(bars.index[0], bars.index[-1]))
        if span_weekdays == 0:
            return None
        return min(1.0, len(bars) / span_weekdays)


class ListingAgeFactor(Factor):
    """Log bar count over the full lookback — proxy for listing age/maturity."""

    name = "listing_age"

    def compute(self, ctx: FactorContext) -> float | None:
        n = len(ctx.prices)
        if n == 0:
            return None
        return math.log(n)


class FundamentalsCoverageFactor(Factor):
    """Share of key fundamental fields populated, discounted by staleness."""

    name = "fundamentals_coverage"

    def compute(self, ctx: FactorContext) -> float | None:
        fundamentals = ctx.fundamentals
        if not fundamentals:
            return 0.0
        populated = sum(
            1 for field in _KEY_FUNDAMENTAL_FIELDS if fundamentals.get(field) is not None
        )
        coverage = populated / len(_KEY_FUNDAMENTAL_FIELDS)

        staleness_discount = 1.0
        report_date = fundamentals.get("filing_date") or fundamentals.get("report_period")
        if report_date:
            try:
                age_days = (
                    datetime.strptime(ctx.as_of, "%Y-%m-%d")
                    - datetime.strptime(str(report_date)[:10], "%Y-%m-%d")
                ).days
                # Full credit inside a quarter; linear decay to 0 at one year.
                staleness_discount = max(0.0, min(1.0, (365.0 - age_days) / (365.0 - 90.0)))
            except ValueError:
                pass
        return coverage * staleness_discount


class NewsCoverageFactor(Factor):
    """Log news article count over the trailing month (attention proxy)."""

    name = "news_coverage"

    def compute(self, ctx: FactorContext) -> float | None:
        if ctx.news_count_30d is None:
            return None
        return math.log1p(max(0, ctx.news_count_30d))
