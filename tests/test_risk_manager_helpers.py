"""Tests for risk manager helper functions.

Tests the pure, deterministic functions in src/agents/risk_manager.py:
- calculate_volatility_adjusted_limit
- calculate_correlation_multiplier
- calculate_volatility_metrics
"""

import numpy as np
import pandas as pd
import pytest

from src.agents.risk_manager import (
    calculate_correlation_multiplier,
    calculate_volatility_adjusted_limit,
    calculate_volatility_metrics,
)


class TestCalculateVolatilityAdjustedLimit:
    """Verify the tiered volatility-based position limit logic."""

    def test_low_volatility_gets_highest_allocation(self):
        # < 15% annualized → multiplier 1.25 → 25% of portfolio
        result = calculate_volatility_adjusted_limit(0.10)
        assert result == pytest.approx(0.20 * 1.25)

    def test_boundary_at_15_percent(self):
        # Exactly 15% → enters medium tier, multiplier = 1.0
        result = calculate_volatility_adjusted_limit(0.15)
        assert result == pytest.approx(0.20 * 1.0)

    def test_medium_volatility_25_percent(self):
        # 25% → multiplier = 1.0 - (0.25 - 0.15) * 0.5 = 0.95
        result = calculate_volatility_adjusted_limit(0.25)
        assert result == pytest.approx(0.20 * 0.95)

    def test_boundary_at_30_percent(self):
        # 30% → enters high tier, multiplier = 0.75 - 0 = 0.75
        result = calculate_volatility_adjusted_limit(0.30)
        assert result == pytest.approx(0.20 * 0.75)

    def test_high_volatility_40_percent(self):
        # 40% → multiplier = 0.75 - (0.40 - 0.30) * 0.5 = 0.70
        result = calculate_volatility_adjusted_limit(0.40)
        assert result == pytest.approx(0.20 * 0.70)

    def test_very_high_volatility_above_50_percent(self):
        # > 50% → multiplier capped at 0.50
        result = calculate_volatility_adjusted_limit(0.80)
        assert result == pytest.approx(0.20 * 0.50)

    def test_zero_volatility(self):
        result = calculate_volatility_adjusted_limit(0.0)
        assert result == pytest.approx(0.20 * 1.25)

    def test_multiplier_never_below_floor(self):
        # The function clamps multiplier to [0.25, 1.25]
        # Very high volatility → raw multiplier could be low, but clamped to 0.25
        result = calculate_volatility_adjusted_limit(100.0)
        assert result >= 0.20 * 0.25

    def test_multiplier_never_above_ceiling(self):
        result = calculate_volatility_adjusted_limit(-1.0)
        assert result <= 0.20 * 1.25


class TestCalculateCorrelationMultiplier:
    """Verify the tiered correlation adjustment."""

    def test_very_high_correlation(self):
        assert calculate_correlation_multiplier(0.90) == 0.70

    def test_high_correlation(self):
        assert calculate_correlation_multiplier(0.70) == 0.85

    def test_moderate_correlation(self):
        assert calculate_correlation_multiplier(0.50) == 1.00

    def test_low_correlation(self):
        assert calculate_correlation_multiplier(0.30) == 1.05

    def test_very_low_correlation(self):
        assert calculate_correlation_multiplier(0.10) == 1.10

    def test_negative_correlation(self):
        assert calculate_correlation_multiplier(-0.50) == 1.10

    def test_exact_boundaries(self):
        assert calculate_correlation_multiplier(0.80) == 0.70
        assert calculate_correlation_multiplier(0.60) == 0.85
        assert calculate_correlation_multiplier(0.40) == 1.00
        assert calculate_correlation_multiplier(0.20) == 1.05

    def test_correlation_at_one(self):
        assert calculate_correlation_multiplier(1.0) == 0.70

    def test_correlation_at_zero(self):
        assert calculate_correlation_multiplier(0.0) == 1.10


class TestCalculateVolatilityMetrics:
    """Test the volatility metrics calculation from price DataFrames."""

    def _make_prices_df(self, closes: list[float]) -> pd.DataFrame:
        dates = pd.date_range("2024-01-01", periods=len(closes), freq="B")
        return pd.DataFrame({"close": closes}, index=dates)

    def test_single_price_returns_defaults(self):
        df = self._make_prices_df([100.0])
        result = calculate_volatility_metrics(df)
        assert result["daily_volatility"] == 0.05
        assert result["annualized_volatility"] == pytest.approx(0.05 * np.sqrt(252))

    def test_empty_df_returns_defaults(self):
        df = pd.DataFrame({"close": []})
        result = calculate_volatility_metrics(df)
        assert result["daily_volatility"] == 0.05
        assert result["volatility_percentile"] == 100

    def test_constant_prices_zero_volatility(self):
        df = self._make_prices_df([100.0] * 10)
        result = calculate_volatility_metrics(df)
        assert result["daily_volatility"] == pytest.approx(0.0, abs=1e-10)
        assert result["annualized_volatility"] == pytest.approx(0.0, abs=1e-10)

    def test_increasing_prices_reasonable_volatility(self):
        # Linear increase: small daily returns, low vol
        closes = [100.0 + i for i in range(60)]
        df = self._make_prices_df(closes)
        result = calculate_volatility_metrics(df)
        assert 0.0 < result["daily_volatility"] < 0.05
        assert result["data_points"] == 59  # lookback_days clips to available

    def test_volatile_prices_high_volatility(self):
        # Alternating +10% / -10% swings
        closes = [100.0]
        for i in range(59):
            closes.append(closes[-1] * (1.10 if i % 2 == 0 else 0.90))
        df = self._make_prices_df(closes)
        result = calculate_volatility_metrics(df)
        assert result["daily_volatility"] > 0.05

    def test_lookback_days_respected(self):
        # 100 data points, lookback 20
        closes = [100.0 + np.random.randn() for _ in range(100)]
        df = self._make_prices_df(closes)
        result = calculate_volatility_metrics(df, lookback_days=20)
        assert result["data_points"] == 20

    def test_nan_handling(self):
        """If std produces NaN (shouldn't normally), fallback values used."""
        df = self._make_prices_df([100.0, 100.0])
        result = calculate_volatility_metrics(df)
        # With only 1 return, std is NaN for ddof=1. Function should handle this.
        assert isinstance(result["daily_volatility"], float)
        assert not np.isnan(result["daily_volatility"])
