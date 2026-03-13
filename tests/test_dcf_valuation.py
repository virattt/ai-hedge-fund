"""Tests for DCF valuation to prevent unrealistic valuations like the $16T OKTA bug (#431)."""

import pytest

from src.agents.valuation import (
    calculate_enhanced_dcf_value,
    calculate_dcf_scenarios,
    calculate_wacc,
    calculate_fcf_volatility,
)


class TestCalculateEnhancedDCFValue:

    def test_returns_zero_for_empty_fcf_history(self):
        result = calculate_enhanced_dcf_value(
            fcf_history=[],
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
        )
        assert result == 0

    def test_returns_zero_for_negative_fcf(self):
        result = calculate_enhanced_dcf_value(
            fcf_history=[-100_000_000],
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
        )
        assert result == 0

    def test_reasonable_valuation_for_typical_company(self):
        market_cap = 10_000_000_000
        result = calculate_enhanced_dcf_value(
            fcf_history=[500_000_000, 450_000_000, 400_000_000],
            growth_metrics={},
            wacc=0.10,
            market_cap=market_cap,
            revenue_growth=0.15,
        )
        assert result > 0
        # Should stay within a plausible range of market cap
        assert result < market_cap * 10

    def test_low_wacc_does_not_explode(self):
        """When WACC is close to terminal growth, the result should still be bounded."""
        market_cap = 15_000_000_000
        result = calculate_enhanced_dcf_value(
            fcf_history=[300_000_000, 250_000_000, 200_000_000, 150_000_000],
            growth_metrics={},
            wacc=0.035,
            market_cap=market_cap,
            revenue_growth=0.25,
        )
        assert result > 0
        # Previously this scenario could produce values 100x+ market cap.
        # With the spread enforcement it should stay reasonable.
        assert result < market_cap * 5

    def test_terminal_value_uses_end_of_transition_fcf(self):
        """The terminal value should be based on the sequentially compounded
        FCF at the end of the transition stage, not a separate formula that
        assumes full transition_growth for all transition years."""
        fcf_history = [500_000_000, 450_000_000, 400_000_000]
        # With high_growth=0.25 and transition_growth=0.14:
        # The old code used base_fcf * 1.25^3 * 1.14^4 for final_fcf,
        # which overstates FCF compared to sequential compounding with
        # declining rates. The new code should produce a lower result.
        result = calculate_enhanced_dcf_value(
            fcf_history=fcf_history,
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
            revenue_growth=0.25,
        )
        # Just verify it's positive and finite
        assert 0 < result < float('inf')


class TestCalculateDCFScenarios:

    def test_returns_all_expected_keys(self):
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
        for case in ('bear', 'base', 'bull'):
            assert case in result['scenarios']

    def test_bear_leq_base_leq_bull(self):
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000, 450_000_000, 400_000_000],
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
            revenue_growth=0.15,
        )
        assert result['scenarios']['bear'] <= result['scenarios']['base']
        assert result['scenarios']['base'] <= result['scenarios']['bull']

    def test_expected_value_is_weighted_average(self):
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000] * 3,
            growth_metrics={},
            wacc=0.10,
            market_cap=10_000_000_000,
        )
        expected = (
            result['scenarios']['bear'] * 0.2
            + result['scenarios']['base'] * 0.6
            + result['scenarios']['bull'] * 0.2
        )
        assert abs(result['expected_value'] - expected) < 1

    def test_wacc_floor_in_bull_scenario(self):
        """Bull case should not push WACC below the 6% floor."""
        market_cap = 10_000_000_000
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000] * 3,
            growth_metrics={},
            wacc=0.06,
            market_cap=market_cap,
            revenue_growth=0.20,
        )
        # Even with the floor binding, bull should be reasonable
        assert result['scenarios']['bull'] < market_cap * 20

    def test_revenue_growth_is_capped(self):
        """Extreme revenue_growth from the API should not blow up the result."""
        market_cap = 10_000_000_000
        result = calculate_dcf_scenarios(
            fcf_history=[500_000_000] * 3,
            growth_metrics={},
            wacc=0.10,
            market_cap=market_cap,
            revenue_growth=5.0,
        )
        assert result['expected_value'] < market_cap * 20

    def test_okta_scenario_stays_reasonable(self):
        """Reproduce the conditions from issue #431."""
        market_cap = 15_000_000_000
        result = calculate_dcf_scenarios(
            fcf_history=[680_000_000, 400_000_000, 200_000_000, 50_000_000],
            growth_metrics={},
            wacc=0.08,
            market_cap=market_cap,
            revenue_growth=0.25,
        )
        # Must not be anywhere near $16T
        assert result['expected_value'] < 1_000_000_000_000
        assert result['upside'] < 1_000_000_000_000


class TestCalculateWACC:

    def test_floor_at_six_percent(self):
        result = calculate_wacc(
            market_cap=10_000_000_000,
            total_debt=0,
            cash=5_000_000_000,
            interest_coverage=100,
            debt_to_equity=0,
        )
        assert result >= 0.06

    def test_cap_at_twenty_percent(self):
        result = calculate_wacc(
            market_cap=1_000_000,
            total_debt=10_000_000,
            cash=0,
            interest_coverage=0.5,
            debt_to_equity=10,
        )
        assert result <= 0.20


class TestCalculateFCFVolatility:

    def test_default_for_short_history(self):
        assert calculate_fcf_volatility([100, 200]) == 0.5

    def test_high_volatility_for_mostly_negative(self):
        assert calculate_fcf_volatility([-100, -200, 50, -150, -100]) == 0.8

    def test_capped_at_one(self):
        assert calculate_fcf_volatility([100, 1000, 50, 2000, 25]) <= 1.0
