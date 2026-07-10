"""Liquidity and transaction-cost factors.

We have no historical quote data, so spread is estimated from daily
high/low bars (Corwin & Schultz 2012). All values are oriented so that
cheaper-to-trade names score higher.
"""

from __future__ import annotations

import math

import numpy as np

from integrations.universe.factors.base import Factor, FactorContext

_WINDOW = 252
_DV_WINDOW = 63


class DollarVolumeFactor(Factor):
    """Log median daily dollar volume — the core capacity measure."""

    name = "dollar_volume"

    def compute(self, ctx: FactorContext) -> float | None:
        recent = ctx.dollar_volume.tail(_DV_WINDOW)
        median = float(recent.median())
        if not math.isfinite(median) or median <= 0:
            return None
        return math.log(median)


class AmihudIlliquidityFactor(Factor):
    """Amihud (2002) price impact: mean |return| per dollar traded (negated)."""

    name = "amihud_illiquidity"

    def compute(self, ctx: FactorContext) -> float | None:
        returns = ctx.returns.tail(_WINDOW)
        dollar_volume = ctx.dollar_volume.tail(_WINDOW).reindex(returns.index)
        valid = dollar_volume > 0
        if valid.sum() < 60:
            return None
        impact = (returns[valid].abs() / dollar_volume[valid]).mean()
        if impact <= 0 or not math.isfinite(impact):
            return None
        return -math.log(impact)


class EstimatedSpreadFactor(Factor):
    """Corwin-Schultz high-low bid-ask spread estimator (negated)."""

    name = "estimated_spread"

    def compute(self, ctx: FactorContext) -> float | None:
        bars = ctx.prices.tail(_WINDOW)
        if len(bars) < 60:
            return None
        high = bars["high"].to_numpy(dtype=float)
        low = bars["low"].to_numpy(dtype=float)
        if np.any(high <= 0) or np.any(low <= 0):
            return None

        log_hl = np.log(high / low) ** 2
        beta = log_hl[:-1] + log_hl[1:]
        high2 = np.maximum(high[:-1], high[1:])
        low2 = np.minimum(low[:-1], low[1:])
        gamma = np.log(high2 / low2) ** 2

        denom = 3.0 - 2.0 * math.sqrt(2.0)
        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / denom - np.sqrt(gamma / denom)
        spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
        spread = np.clip(spread, 0.0, None)  # negative estimates mean ~zero spread
        mean_spread = float(np.nanmean(spread))
        if not math.isfinite(mean_spread):
            return None
        return -mean_spread


class ZeroVolumeDaysFactor(Factor):
    """Count of no-trade days in the past year (negated)."""

    name = "zero_volume_days"

    def compute(self, ctx: FactorContext) -> float | None:
        volume = ctx.prices["volume"].tail(_WINDOW)
        return -float((volume <= 0).sum())
