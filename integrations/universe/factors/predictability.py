"""Statistical predictability factors.

These reward return series with exploitable structure — momentum or
mean-reversion that deviates from a random walk — and, critically, structure
that PERSISTS: every measure is paired with a stability check across the two
halves of the window, because structure that appears once is noise.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from integrations.universe.factors.base import Factor, FactorContext

_WINDOW = 252
_VR_LAG = 5
_ER_WINDOW = 21


def _autocorr(returns: pd.Series) -> float | None:
    if len(returns) < 60:
        return None
    value = returns.autocorr(lag=1)
    return float(value) if value is not None and math.isfinite(value) else None


def variance_ratio(returns: pd.Series, lag: int = _VR_LAG) -> float | None:
    """Lo-MacKinlay variance ratio: Var(k-day returns) / (k * Var(1-day))."""
    if len(returns) < lag * 20:
        return None
    var_1 = float(returns.var())
    if var_1 <= 0:
        return None
    multi = returns.rolling(lag).sum().dropna()
    var_k = float(multi.var())
    ratio = var_k / (lag * var_1)
    return ratio if math.isfinite(ratio) else None


def efficiency_ratio(closes: pd.Series, window: int = _ER_WINDOW) -> float | None:
    """Kaufman efficiency ratio: |net move| / path length, averaged."""
    if len(closes) < window * 3:
        return None
    net = closes.diff(window).abs()
    path = closes.diff().abs().rolling(window).sum()
    ratio = (net / path).replace([np.inf, -np.inf], np.nan).dropna()
    if ratio.empty:
        return None
    return float(ratio.mean())


class AutocorrelationFactor(Factor):
    """|lag-1 autocorrelation| — either momentum or mean-reversion is usable."""

    name = "autocorrelation"

    def compute(self, ctx: FactorContext) -> float | None:
        ac = _autocorr(ctx.returns.tail(_WINDOW))
        return abs(ac) if ac is not None else None


class VarianceRatioFactor(Factor):
    """|VR(5) - 1| — deviation from a random walk in either direction."""

    name = "variance_ratio"

    def compute(self, ctx: FactorContext) -> float | None:
        vr = variance_ratio(ctx.returns.tail(_WINDOW))
        return abs(vr - 1.0) if vr is not None else None


class EfficiencyRatioFactor(Factor):
    """Trendiness: how directly price travels rather than chopping."""

    name = "efficiency_ratio"

    def compute(self, ctx: FactorContext) -> float | None:
        return efficiency_ratio(ctx.prices["close"].tail(_WINDOW))


class StatStabilityFactor(Factor):
    """Negative drift of (autocorr, vol) between the window's two halves."""

    name = "stat_stability"

    def compute(self, ctx: FactorContext) -> float | None:
        returns = ctx.returns.tail(_WINDOW)
        if len(returns) < 120:
            return None
        half = len(returns) // 2
        first, second = returns.iloc[:half], returns.iloc[half:]

        ac_a, ac_b = _autocorr(first), _autocorr(second)
        vol_a, vol_b = float(first.std()), float(second.std())
        if ac_a is None or ac_b is None or vol_a <= 0 or vol_b <= 0:
            return None

        ac_drift = abs(ac_a - ac_b)
        vol_drift = abs(vol_a - vol_b) / ((vol_a + vol_b) / 2.0)
        return -(ac_drift + vol_drift)
