"""Alpha Learnability as a scoring factor.

The heavy lifting (signal replay, IC, regime consistency) happens in
``integrations/universe/learnability.py``; the pipeline attaches each
ticker's ``LearnabilityResult`` to its FactorContext and this factor simply
exposes the score to the scoring engine.
"""

from __future__ import annotations

from integrations.universe.factors.base import Factor, FactorContext


class AlphaLearnabilityFactor(Factor):
    """Shrunken, regime-consistent IC of our own pipeline on this stock."""

    name = "alpha_learnability"

    def compute(self, ctx: FactorContext) -> float | None:
        result = ctx.learnability
        if result is None:
            return None
        return float(result.score)
