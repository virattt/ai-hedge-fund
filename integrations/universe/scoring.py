"""Cross-sectional scoring engine: winsorize -> z-score -> weighted composite.

The engine is deliberately dumb about finance: factors emit oriented raw
values (higher = better) and this module only does the statistics. Missing
values score neutral (z = 0) so a ticker isn't rewarded or punished for a
factor we couldn't compute — but the miss is recorded in the breakdown.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from integrations.universe.factors.base import Factor, FactorContext
from integrations.universe.models import FactorScore, TickerScore

logger = logging.getLogger(__name__)

_WINSOR_PCT = 2.5  # clip raw values at the 2.5th/97.5th percentile


def winsorize(values: np.ndarray, pct: float = _WINSOR_PCT) -> np.ndarray:
    if values.size == 0:
        return values
    lo, hi = np.percentile(values, [pct, 100.0 - pct])
    return np.clip(values, lo, hi)


def zscores(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    clipped = winsorize(values.astype(float))
    std = float(clipped.std())
    if std <= 1e-12:
        return np.zeros_like(clipped)
    return (clipped - float(clipped.mean())) / std


def score_candidates(
    contexts: dict[str, FactorContext],
    factors: list[Factor],
    weights: dict[str, float],
) -> list[TickerScore]:
    """Score every context against every factor; return ranked TickerScores."""
    tickers = list(contexts)
    active = [f for f in factors if weights.get(f.name, 0.0) > 0.0]

    # raw[factor][i] aligned with tickers; NaN = not computable
    raw: dict[str, np.ndarray] = {}
    for factor in active:
        column = np.full(len(tickers), np.nan)
        for i, ticker in enumerate(tickers):
            try:
                value = factor.compute(contexts[ticker])
            except Exception as exc:
                logger.debug("Factor %s failed for %s: %s", factor.name, ticker, exc)
                value = None
            if value is not None and math.isfinite(value):
                column[i] = float(value)
        raw[factor.name] = column

    # z-score each factor over its non-missing values
    z: dict[str, np.ndarray] = {}
    for name, column in raw.items():
        scored = np.zeros(len(tickers))
        mask = ~np.isnan(column)
        if mask.sum() >= 2:
            scored[mask] = zscores(column[mask])
        z[name] = scored

    total_weight = sum(weights[f.name] for f in active) or 1.0

    results: list[TickerScore] = []
    for i, ticker in enumerate(tickers):
        breakdown: dict[str, FactorScore] = {}
        composite = 0.0
        for factor in active:
            weight = weights[factor.name]
            raw_value = raw[factor.name][i]
            zscore = float(z[factor.name][i])
            composite += weight * zscore
            breakdown[factor.name] = FactorScore(
                name=factor.name,
                raw=None if np.isnan(raw_value) else float(raw_value),
                zscore=zscore,
                weight=weight,
            )
        results.append(
            TickerScore(
                ticker=ticker,
                composite=composite / total_weight,
                sector=contexts[ticker].sector,
                factors=breakdown,
            )
        )

    results.sort(key=lambda s: s.composite, reverse=True)
    for rank, score in enumerate(results, start=1):
        score.rank = rank
    return results
