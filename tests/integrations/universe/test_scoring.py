"""Scoring engine tests: winsorize, z-score, weighting, missing values."""

from __future__ import annotations

import numpy as np

from integrations.universe.factors.base import Factor, FactorContext
from integrations.universe.scoring import score_candidates, winsorize, zscores

from tests.integrations.universe.universe_fixtures import make_context, make_prices


class ConstantFactor(Factor):
    def __init__(self, name: str, values: dict[str, float | None]) -> None:
        self.name = name
        self._values = values

    def compute(self, ctx: FactorContext) -> float | None:
        return self._values.get(ctx.ticker)


def _contexts(tickers: list[str]) -> dict[str, FactorContext]:
    return {t: make_context(t, make_prices(seed=i)) for i, t in enumerate(tickers)}


def test_winsorize_clips_outliers():
    values = np.array([1.0] * 98 + [1000.0, -1000.0])
    clipped = winsorize(values)
    assert clipped.max() < 1000.0
    assert clipped.min() > -1000.0


def test_zscores_standardize():
    z = zscores(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
    assert abs(z.mean()) < 1e-9
    assert z[-1] > z[0]


def test_zscores_constant_column_is_neutral():
    z = zscores(np.array([2.0, 2.0, 2.0]))
    assert np.allclose(z, 0.0)


def test_composite_orders_by_weighted_factors():
    tickers = ["AAA", "BBB", "CCC"]
    contexts = _contexts(tickers)
    factors = [
        ConstantFactor("good", {"AAA": 3.0, "BBB": 2.0, "CCC": 1.0}),
        ConstantFactor("noise", {"AAA": 1.0, "BBB": 1.0, "CCC": 1.0}),
    ]
    scores = score_candidates(contexts, factors, {"good": 1.0, "noise": 1.0})
    assert [s.ticker for s in scores] == ["AAA", "BBB", "CCC"]
    assert scores[0].rank == 1 and scores[-1].rank == 3


def test_zero_weight_disables_factor():
    tickers = ["AAA", "BBB"]
    contexts = _contexts(tickers)
    factors = [ConstantFactor("only", {"AAA": 1.0, "BBB": 100.0})]
    scores = score_candidates(contexts, factors, {"only": 0.0})
    assert all(s.composite == 0.0 for s in scores)
    assert all("only" not in s.factors for s in scores)


def test_missing_value_scores_neutral():
    tickers = ["AAA", "BBB", "CCC"]
    contexts = _contexts(tickers)
    factors = [ConstantFactor("partial", {"AAA": 10.0, "BBB": -10.0, "CCC": None})]
    scores = {s.ticker: s for s in score_candidates(contexts, factors, {"partial": 1.0})}
    assert scores["CCC"].factors["partial"].raw is None
    assert scores["CCC"].factors["partial"].zscore == 0.0
    assert scores["AAA"].composite > scores["CCC"].composite > scores["BBB"].composite


def test_factor_exception_treated_as_missing():
    class ExplodingFactor(Factor):
        name = "boom"

        def compute(self, ctx: FactorContext) -> float | None:
            raise RuntimeError("boom")

    contexts = _contexts(["AAA", "BBB"])
    scores = score_candidates(contexts, [ExplodingFactor()], {"boom": 1.0})
    assert all(s.factors["boom"].raw is None for s in scores)
