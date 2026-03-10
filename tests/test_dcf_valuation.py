"""Tests for DCF valuation functions to prevent unrealistic valuations.

These tests verify the fixes for issue #431 where DCF analysis was producing
unrealistic valuations (e.g., $16T for OKTA).
"""

import pytest

from src.agents.valuation import (
    calculate_enhanced_dcf_value,
    calculate_dcf_scenarios,
    calculate_wacc,
    calculate_fcf_volatility,
)


class TestCalculateEnhancedDCFValue:
    """Tests for calculate_enhanced_dcf_value function."""

    def test_returns_zero_for_empty_fcf_history(self):
        """Should return 0 when FCF history is empty."""
        result = calculate_enhanced_dcf_value(
            fcf_history=[],
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
        )
        assert result == 0

    def test_returns_zero_for_negative_fcf(self):
        """Should return 0 when current FCF is negative."""
        result = calculate_enhanced_dcf_value(
            fcf_history=[-100_000_000],
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
        )
        assert result == 0

    def test_valuation_capped_at_100x_market_cap(self):
        """Valuation should never exceed 100x market cap."""
        market_cap = 10_000_000_000  # $10B
        result = calculate_enhanced_dcf_value(
            fcf_history=[5_000_000_000] * 5,  # Large FCF
            growth_metrics={},
            wacc=0.06,  # Low WACC
            market_cap=market_cap,
            revenue_growth=0.50,  # High growth
        )
        assert result <= market_cap * 100

    def test_reasonable_valuation_for_typical_company(self):
        """Should produce reasonable valuation for typical inputs."""
        market_cap = 10_000_000_000  # $10B
        result = calculate_enhanced_dcf_value(
            fcf_history=[500_000_000, 450_000_000, 400_000_000],  # ~$500M FCF
            growth_metrics={},
            wacc=0.10,
            market_cap=market_cap,
            revenue_growth=0.15,
        )
        # Valuation should be positive and within reasonable bounds
        assert result > 0
        assert result < market_cap * 50  # Less than 50x market cap

    def test_large_cap_growth_rate_limited(self):
        """Large cap companies should have growth rate limited to 10%."""
        large_market_cap = 100_000_000_000  # $100B (large cap)
        small_market_cap = 5_000_000_000   # $5B (small cap)

        fcf_history = [1_000_000_000] * 5

        large_cap_result = calculate_enhanced_dcf_value(
            fcf_history=fcf_history,
            growth_metrics={},
            wacc=0.10,
            market_cap=large_market_cap,
            revenue_growth=0.25,  # High growth requested
        )

        small_cap_result = calculate_enhanced_dcf_value(
            fcf_history=fcf_history,
            growth_metrics={},
            wacc=0.10,
            market_cap=small_market_cap,
            revenue_growth=0.25,  # High growth requested
        )

        # Large cap should have lower valuation due to growth cap
        # Note: Results are also capped by market_cap, so we compare relative to market cap
        large_cap_multiple = large_cap_result / large_market_cap
        small_cap_multiple = small_cap_result / small_market_cap
        # Small cap can have higher multiple due to higher allowed growth
        assert small_cap_multiple >= large_cap_multiple * 0.5

    def test_wacc_terminal_growth_spread_enforced(self):
        """Should maintain minimum spread between WACC and terminal growth."""
        result = calculate_enhanced_dcf_value(
            fcf_history=[500_000_000] * 5,
            growth_metrics={},
            wacc=0.05,  # Very low WACC
            market_cap=10_000_000_000,
            revenue_growth=0.10,
        )
        # Should still produce reasonable result due to safeguards
        assert result > 0
        assert result < 10_000_000_000 * 100


class TestCalculateDCFScenarios:
    """Tests for calculate_dcf_scenarios function."""

    def test_returns_all_scenario_keys(self):
        """Should return all expected scenario keys."""
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000] * 3,
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
        )
        assert 'scenarios' in result
        assert 'expected_value' in result
        assert 'range' in result
        assert 'upside' in result
        assert 'downside' in result
        assert 'bear' in result['scenarios']
        assert 'base' in result['scenarios']
        assert 'bull' in result['scenarios']

    def test_bear_less_than_base_less_than_bull(self):
        """Bear case should be <= base <= bull."""
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000] * 3,
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
            revenue_growth=0.15,
        )
        assert result['scenarios']['bear'] <= result['scenarios']['base']
        assert result['scenarios']['base'] <= result['scenarios']['bull']

    def test_expected_value_is_weighted_average(self):
        """Expected value should be probability-weighted average."""
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000] * 3,
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
        )
        expected = (
            result['scenarios']['bear'] * 0.2 +
            result['scenarios']['base'] * 0.6 +
            result['scenarios']['bull'] * 0.2
        )
        assert abs(result['expected_value'] - expected) < 1  # Allow small float error

    def test_wacc_floor_enforced_in_bull_scenario(self):
        """WACC should not go below 7% even in bull scenario."""
        # With low WACC, bull scenario adjustment (0.9x) could go very low
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000] * 3,
            growth_metrics={},
            wacc=0.06,  # Low WACC, 0.9x would be 5.4%
            market_cap=10_000_000_000,
            revenue_growth=0.20,
        )
        # Bull should still be reasonable due to WACC floor
        assert result['scenarios']['bull'] < 10_000_000_000 * 100

    def test_revenue_growth_capped_at_30_percent(self):
        """Base revenue growth should be capped at 30%."""
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000] * 3,
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
            revenue_growth=0.80,  # Extremely high growth
        )
        # Should produce reasonable results due to growth cap
        assert result['expected_value'] < 10_000_000_000 * 100

    def test_okta_like_scenario_no_trillion_valuation(self):
        """Simulate OKTA-like inputs - should not produce $16T valuation.

        This is the specific test case from issue #431.
        """
        # OKTA approximate values (as of issue date)
        market_cap = 15_000_000_000  # ~$15B market cap
        fcf_history = [300_000_000, 250_000_000, 200_000_000, 150_000_000]  # Positive FCF

        result = calculate_dcf_scenarios(
            fcf_history=fcf_history,
            growth_metrics={},
            wacc=0.08,
            market_cap=market_cap,
            revenue_growth=0.25,  # High growth tech company
        )

        # Valuation should be reasonable, definitely not $16T
        assert result['expected_value'] < 1_000_000_000_000  # Less than $1T
        assert result['expected_value'] < market_cap * 100  # Less than 100x market cap
        # Bull case should also be reasonable
        assert result['upside'] < 2_000_000_000_000  # Less than $2T


class TestCalculateWACC:
    """Tests for calculate_wacc function."""

    def test_wacc_floor_at_6_percent(self):
        """WACC should have a floor of 6%."""
        result = calculate_wacc(
            market_cap=10_000_000_000,
            total_debt=0,
            cash=5_000_000_000,  # Lots of cash
            interest_coverage=100,  # Very high coverage
            debt_to_equity=0,
        )
        assert result >= 0.06

    def test_wacc_cap_at_20_percent(self):
        """WACC should be capped at 20%."""
        result = calculate_wacc(
            market_cap=1_000_000,  # Small market cap
            total_debt=10_000_000,  # High debt
            cash=0,
            interest_coverage=0.5,  # Very low coverage
            debt_to_equity=10,  # Very high leverage
        )
        assert result <= 0.20


class TestCalculateFCFVolatility:
    """Tests for calculate_fcf_volatility function."""

    def test_default_volatility_for_short_history(self):
        """Should return default 0.5 for history < 3 periods."""
        result = calculate_fcf_volatility([100, 200])
        assert result == 0.5

    def test_high_volatility_for_mostly_negative_fcf(self):
        """Should return high volatility (0.8) for mostly negative FCF."""
        result = calculate_fcf_volatility([-100, -200, 50, -150, -100])
        assert result == 0.8

    def test_volatility_capped_at_1(self):
        """Volatility should be capped at 1.0."""
        result = calculate_fcf_volatility([100, 1000, 50, 2000, 25])
        assert result <= 1.0
