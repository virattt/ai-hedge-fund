"""Diversified selection tests: sector caps, correlation limits, relaxation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from integrations.universe.config import UniverseConfig
from integrations.universe.models import TickerScore
from integrations.universe.select import returns_matrix, select_universe

from tests.integrations.universe.universe_fixtures import make_prices, trading_calendar


def _score(ticker: str, composite: float, sector: str = "TECH") -> TickerScore:
    return TickerScore(ticker=ticker, composite=composite, sector=sector)


def _frames(tickers: list[str], seed_offset: int = 0) -> dict[str, pd.DataFrame]:
    return {t: make_prices(seed=i + seed_offset) for i, t in enumerate(tickers)}


def test_selects_top_scores_when_unconstrained():
    tickers = [f"T{i}" for i in range(10)]
    scores = [_score(t, 10 - i, sector=f"S{i}") for i, t in enumerate(tickers)]
    config = UniverseConfig(size=5, max_correlation=0.99)
    selected = select_universe(scores, _frames(tickers), config)
    assert selected == tickers[:5]


def test_sector_cap_enforced():
    # 6 high-scoring TECH names, cap allows ceil(4 * 0.5) = 2 per sector.
    scores = [_score(f"TECH{i}", 100 - i, "TECH") for i in range(6)]
    scores += [_score(f"FIN{i}", 10 - i, "FIN") for i in range(4)]
    tickers = [s.ticker for s in scores]
    config = UniverseConfig(size=4, sector_cap_pct=0.5, max_correlation=0.999)
    selected = select_universe(scores, _frames(tickers), config)
    assert sum(1 for t in selected if t.startswith("TECH")) == 2
    assert sum(1 for t in selected if t.startswith("FIN")) == 2


def test_correlation_limit_rejects_clones():
    calendar = trading_calendar(300)
    rng = np.random.default_rng(42)
    base_returns = rng.normal(0, 0.02, 300)

    def frame_from_returns(returns: np.ndarray) -> pd.DataFrame:
        closes = 100 * np.exp(np.cumsum(returns))
        return pd.DataFrame(
            {"open": closes, "high": closes, "low": closes, "close": closes,
             "volume": np.full(300, 1e6)},
            index=calendar,
        )

    frames = {
        "ORIG": frame_from_returns(base_returns),
        "CLONE": frame_from_returns(base_returns + rng.normal(0, 0.0005, 300)),
        "INDEP": frame_from_returns(rng.normal(0, 0.02, 300)),
    }
    scores = [_score("ORIG", 3.0, "A"), _score("CLONE", 2.0, "B"), _score("INDEP", 1.0, "C")]
    config = UniverseConfig(size=2, max_correlation=0.90)
    selected = select_universe(scores, frames, config)
    assert selected == ["ORIG", "INDEP"]


def test_relaxation_fills_target_size():
    # All same sector with a tiny cap: strict pass can't fill 4 slots,
    # relaxation passes must.
    scores = [_score(f"T{i}", 10 - i, "TECH") for i in range(6)]
    tickers = [s.ticker for s in scores]
    config = UniverseConfig(size=4, sector_cap_pct=0.25, max_correlation=0.99)
    selected = select_universe(scores, _frames(tickers), config)
    assert len(selected) == 4


def test_returns_matrix_alignment():
    frames = _frames(["A", "B"])
    matrix = returns_matrix(frames, 100)
    assert set(matrix.columns) == {"A", "B"}
    assert len(matrix) <= 101
