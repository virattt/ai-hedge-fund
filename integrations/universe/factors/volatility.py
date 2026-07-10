"""Tradable-volatility factors.

We don't want the highest-volatility names — we want names whose volatility
is large enough to pay for costs but stable enough for position sizing and
signals to hold up. Volatility is scored as distance from a sweet-spot band,
and unstable volatility regimes are penalized separately.
"""

from __future__ import annotations

import math

import numpy as np

from integrations.universe.factors.base import Factor, FactorContext

_WINDOW = 252
_ROLL = 21
_ANNUALIZE = math.sqrt(252.0)


def annualized_vol(returns) -> float | None:
    if len(returns) < 60:
        return None
    vol = float(returns.std()) * _ANNUALIZE
    return vol if math.isfinite(vol) else None


class VolatilityBandFactor(Factor):
    """Negative distance of annualized vol from the [low, high] sweet spot.

    0 inside the band; increasingly negative the further outside. Too-quiet
    names have nothing to capture, too-wild names are untradable.
    """

    name = "volatility_band"

    def compute(self, ctx: FactorContext) -> float | None:
        vol = annualized_vol(ctx.returns.tail(_WINDOW))
        if vol is None:
            return None
        low, high = ctx.config.vol_band_low, ctx.config.vol_band_high
        if vol < low:
            return -(low - vol)
        if vol > high:
            return -(vol - high)
        return 0.0


class VolStabilityFactor(Factor):
    """Negative vol-of-vol: std of rolling 21d vol over its mean."""

    name = "vol_stability"

    def compute(self, ctx: FactorContext) -> float | None:
        returns = ctx.returns.tail(_WINDOW)
        if len(returns) < _ROLL * 3:
            return None
        rolling = returns.rolling(_ROLL).std().dropna()
        mean = float(rolling.mean())
        if mean <= 0 or not math.isfinite(mean):
            return None
        vol_of_vol = float(rolling.std()) / mean
        if not math.isfinite(vol_of_vol):
            return None
        return -vol_of_vol
