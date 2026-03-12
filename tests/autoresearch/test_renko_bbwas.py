"""Tests for autoresearch.renko_bbwas."""

import numpy as np
import pandas as pd
import pytest

from autoresearch.renko_bbwas import (
    build_renko_bricks,
    classify_regime,
    compute_atr,
    compute_bbwas,
    renko_regime,
    renko_regime_mtf,
    renko_trend_score,
)


def _make_ohlc(closes: list[float], spread: float = 1.0) -> pd.DataFrame:
    """Helper: build a synthetic OHLC DataFrame from a list of closes."""
    dates = pd.date_range("2025-01-01", periods=len(closes), freq="B")
    return pd.DataFrame({
        "open": [c - spread * 0.3 for c in closes],
        "high": [c + spread for c in closes],
        "low": [c - spread for c in closes],
        "close": closes,
    }, index=dates)


class TestComputeATR:
    def test_atr_positive(self):
        df = _make_ohlc([100 + i for i in range(30)])
        atr = compute_atr(df, period=14)
        assert len(atr) == 30
        assert all(atr > 0)

    def test_atr_short_series(self):
        df = _make_ohlc([100, 101, 102])
        atr = compute_atr(df, period=14)
        assert len(atr) == 3
        assert all(atr > 0)


class TestBuildRenkoBricks:
    def test_uptrend(self):
        closes = pd.Series([100 + i * 5 for i in range(20)])
        bricks = build_renko_bricks(closes, brick_size=5.0)
        assert len(bricks) > 0
        assert all(b["direction"] == 1 for b in bricks)

    def test_downtrend(self):
        closes = pd.Series([200 - i * 5 for i in range(20)])
        bricks = build_renko_bricks(closes, brick_size=5.0)
        assert len(bricks) > 0
        assert all(b["direction"] == -1 for b in bricks)

    def test_no_bricks_in_flat_market(self):
        closes = pd.Series([100.0] * 20)
        bricks = build_renko_bricks(closes, brick_size=5.0)
        assert len(bricks) == 0

    def test_brick_size_respected(self):
        closes = pd.Series([100, 103, 106, 109, 112])
        bricks = build_renko_bricks(closes, brick_size=5.0)
        assert len(bricks) == 2
        for b in bricks:
            assert abs(b["end"] - b["start"]) == pytest.approx(5.0)

    def test_reversal(self):
        closes = pd.Series([100, 110, 120, 115, 105, 95])
        bricks = build_renko_bricks(closes, brick_size=5.0)
        directions = [b["direction"] for b in bricks]
        assert 1 in directions
        assert -1 in directions

    def test_empty_series(self):
        assert build_renko_bricks(pd.Series(dtype=float), brick_size=5.0) == []

    def test_zero_brick_size(self):
        assert build_renko_bricks(pd.Series([100, 110]), brick_size=0) == []


class TestRenkoTrendScore:
    def test_all_green(self):
        bricks = [{"direction": 1}] * 10
        assert renko_trend_score(bricks, lookback=10) == 1.0

    def test_all_red(self):
        bricks = [{"direction": -1}] * 10
        assert renko_trend_score(bricks, lookback=10) == -1.0

    def test_mixed(self):
        bricks = [{"direction": 1}] * 6 + [{"direction": -1}] * 4
        score = renko_trend_score(bricks, lookback=10)
        assert score == pytest.approx(0.2)

    def test_empty(self):
        assert renko_trend_score([], lookback=10) == 0.0

    def test_lookback_shorter_than_bricks(self):
        bricks = [{"direction": -1}] * 20 + [{"direction": 1}] * 5
        score = renko_trend_score(bricks, lookback=5)
        assert score == 1.0


class TestComputeBBWAS:
    def test_expanding_bands(self):
        # Trending series produces wider bands
        renko_closes = np.array([100 + i * 2 for i in range(30)])
        bbwas = compute_bbwas(renko_closes, bb_period=10)
        assert bbwas["bandwidth"] > 0
        assert bbwas["mid"] > 0

    def test_flat_series(self):
        renko_closes = np.array([100.0] * 30)
        bbwas = compute_bbwas(renko_closes, bb_period=10)
        assert bbwas["bandwidth"] == pytest.approx(0.0, abs=1e-6)

    def test_short_series_returns_defaults(self):
        bbwas = compute_bbwas(np.array([100, 101, 102]), bb_period=20)
        assert bbwas["bandwidth"] == 0.0
        assert bbwas["squeeze"] is False

    def test_squeeze_quality_bounds(self):
        bbwas = compute_bbwas(np.array([100.0] * 40), bb_period=10)
        assert 0.0 <= bbwas["squeeze_quality"] <= 1.0


class TestClassifyRegime:
    def test_trending_bull_expanding(self):
        bbwas = {"squeeze": False, "expanding": True, "bandwidth": 0.1}
        result = classify_regime(0.8, bbwas)
        assert result["regime"] == "trending_bull"
        assert result["scale"] == 1.0

    def test_trending_bear_expanding(self):
        bbwas = {"squeeze": False, "expanding": True, "bandwidth": 0.1}
        result = classify_regime(-0.8, bbwas)
        assert result["regime"] == "trending_bear"
        assert result["scale"] == 0.35

    def test_squeeze_overrides(self):
        bbwas = {"squeeze": True, "expanding": False, "bandwidth": 0.01}
        result = classify_regime(0.8, bbwas)
        assert result["regime"] == "squeeze"
        assert result["direction"] == "neutral"

    def test_neutral_on_mixed_signals(self):
        bbwas = {"squeeze": False, "expanding": False, "bandwidth": 0.05}
        result = classify_regime(0.1, bbwas)
        assert result["regime"] == "neutral"

    def test_confidence_field_present(self):
        bbwas = {"squeeze": False, "expanding": True, "bandwidth": 0.1}
        result = classify_regime(0.8, bbwas)
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0


class TestRenkoRegimeIntegration:
    def test_from_ohlc(self):
        # Provide a clean uptrend
        closes = [100 + i * 2 for i in range(60)]
        df = _make_ohlc(closes, spread=1.5)
        sig = renko_regime("TEST", ohlc_df=df, atr_mult=1.0)
        assert sig["ticker"] == "TEST"
        assert sig["n_bricks"] > 0
        assert sig["direction"] in ("bull", "bear", "neutral")
        assert 0.0 < sig["scale"] <= 1.0

    def test_downtrend_detection(self):
        closes = [300 - i * 3 for i in range(60)]
        df = _make_ohlc(closes, spread=2.0)
        sig = renko_regime("TEST", ohlc_df=df, atr_mult=1.0)
        assert sig["direction"] == "bear"
        assert sig["brick_trend"] < 0

    def test_insufficient_data(self):
        df = _make_ohlc([100, 101, 102])
        sig = renko_regime("TEST", ohlc_df=df)
        assert sig["regime"] == "neutral"
        assert sig["scale"] == 0.6

    def test_missing_ticker_returns_neutral(self):
        sig = renko_regime("ZZZZZZ_NONEXISTENT")
        assert sig["regime"] == "neutral"

    def test_mtf_signal(self):
        closes = [100 + i * 2 for i in range(100)]
        df = _make_ohlc(closes, spread=1.5)
        sig = renko_regime_mtf("TEST", ohlc_df=df, atr_mult_fast=1.0, atr_mult_slow=2.0)
        assert "mtf_confirmed" in sig
        assert "confidence" in sig
