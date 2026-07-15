"""Crowding and shortability factors.

No short-interest feed exists in the current data providers, so crowding is
proxied from price/volume behavior, and shortability comes from the broker's
current borrow flags (documented limitation: those flags are current-state,
not point-in-time).
"""

from __future__ import annotations

import math

from integrations.universe.factors.base import Factor, FactorContext

_BASELINE_WINDOW = 252
_RECENT_WINDOW = 21
_MOMENTUM_WINDOW = 126


class VolumeSurgeFactor(Factor):
    """Penalty for recent dollar volume running far above its 1-year baseline.

    A surge means the name is suddenly hot — crowded, headline-driven, and
    likely to behave unlike the history our signals learned from.
    """

    name = "volume_surge"

    def compute(self, ctx: FactorContext) -> float | None:
        dollar_volume = ctx.dollar_volume
        baseline = float(dollar_volume.tail(_BASELINE_WINDOW).median())
        recent = float(dollar_volume.tail(_RECENT_WINDOW).median())
        if baseline <= 0 or not math.isfinite(recent):
            return None
        surge = recent / baseline
        return -max(0.0, surge - 1.0)


class MomentumExtremenessFactor(Factor):
    """Penalty for extreme trailing 6-month moves in either direction."""

    name = "momentum_extremeness"

    def compute(self, ctx: FactorContext) -> float | None:
        closes = ctx.prices["close"]
        if len(closes) < _MOMENTUM_WINDOW + 1:
            return None
        past = float(closes.iloc[-_MOMENTUM_WINDOW - 1])
        if past <= 0:
            return None
        total_return = float(closes.iloc[-1]) / past
        return -abs(math.log(total_return))


class ShortabilityFactor(Factor):
    """Borrow availability from the broker's asset flags."""

    name = "shortability"

    def compute(self, ctx: FactorContext) -> float | None:
        if ctx.easy_to_borrow:
            return 1.0
        if ctx.shortable:
            return 0.5
        return 0.0
