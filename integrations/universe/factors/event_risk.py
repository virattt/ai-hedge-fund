"""Event-risk factors.

Penalize names whose P&L is dominated by discrete jumps our daily pipeline
cannot anticipate: fat-tailed return distributions, violent overnight gaps,
historically explosive earnings reactions, and earnings landing right on top
of the selection date.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pandas as pd

from integrations.universe.factors.base import Factor, FactorContext

_WINDOW = 252
_EARNINGS_BLACKOUT_DAYS = 7
_TYPICAL_EARNINGS_CYCLE_DAYS = 91


class TailRiskFactor(Factor):
    """Negative excess kurtosis of daily returns."""

    name = "tail_risk"

    def compute(self, ctx: FactorContext) -> float | None:
        returns = ctx.returns.tail(_WINDOW)
        if len(returns) < 60:
            return None
        kurt = float(returns.kurtosis())  # pandas returns excess kurtosis
        if not math.isfinite(kurt):
            return None
        return -max(0.0, kurt)


class MaxGapFactor(Factor):
    """Negative largest absolute overnight gap (open vs prior close)."""

    name = "max_gap"

    def compute(self, ctx: FactorContext) -> float | None:
        bars = ctx.prices.tail(_WINDOW)
        if len(bars) < 60:
            return None
        prior_close = bars["close"].shift(1)
        gaps = ((bars["open"] - prior_close) / prior_close).abs().dropna()
        if gaps.empty:
            return None
        return -float(gaps.max())


class EarningsGapRiskFactor(Factor):
    """Negative mean absolute price move on historical earnings filing dates."""

    name = "earnings_gap_risk"

    def compute(self, ctx: FactorContext) -> float | None:
        if not ctx.earnings_events:
            return None
        closes = ctx.prices["close"]
        daily_move = closes.pct_change().abs()

        moves: list[float] = []
        for event in ctx.earnings_events:
            filing = event.get("filing_date")
            if not filing:
                continue
            filing_ts = pd.Timestamp(str(filing)[:10])
            # Reaction lands on the filing day or the next session.
            window = daily_move.loc[filing_ts : filing_ts + pd.Timedelta(days=4)].head(2)
            if not window.empty:
                moves.append(float(window.max()))
        if not moves:
            return None
        return -(sum(moves) / len(moves))


class EarningsProximityFactor(Factor):
    """Penalty when the next earnings report is likely within days of as_of.

    We have no forward calendar, so the next report is estimated as the last
    filing plus one quarter. Binary: -1 inside the blackout window, else 0.
    """

    name = "earnings_proximity"

    def compute(self, ctx: FactorContext) -> float | None:
        if not ctx.earnings_events:
            return None
        filings = [
            datetime.strptime(str(e["filing_date"])[:10], "%Y-%m-%d")
            for e in ctx.earnings_events
            if e.get("filing_date")
        ]
        if not filings:
            return None
        estimated_next = max(filings) + timedelta(days=_TYPICAL_EARNINGS_CYCLE_DAYS)
        as_of = datetime.strptime(ctx.as_of, "%Y-%m-%d")
        return -1.0 if abs((estimated_next - as_of).days) <= _EARNINGS_BLACKOUT_DAYS else 0.0
