"""Regression tests for valuation sanity bounds (issue #431).

OKTA was valued at $16T because `calculate_owner_earnings_value` had no
cap on `growth_rate`.  Companies transitioning from loss to profit can
report 300-500 %+ earnings growth, which causes the terminal-value
formula to explode.  These tests verify the fix.
"""

from __future__ import annotations

import pytest

from src.agents.valuation import (
    _MAX_GROWTH_RATE,
    _clamp_growth_rate,
    calculate_owner_earnings_value,
    calculate_intrinsic_value,
    calculate_enhanced_dcf_value,
    calculate_dcf_scenarios,
    calculate_residual_income_value,
    calculate_wacc,
    calculate_fcf_volatility,
)


# ---------------------------------------------------------------------------
# _clamp_growth_rate
# ---------------------------------------------------------------------------

class TestClampGrowthRate:
    def test_none_returns_default(self):
        assert _clamp_growth_rate(None) == 0.05

    def test_normal_rate_unchanged(self):
        assert _clamp_growth_rate(0.10) == 0.10

    def test_negative_clamped_to_floor(self):
        assert _clamp_growth_rate(-0.5) == 0.0

    def test_excessive_rate_clamped(self):
        assert _clamp_growth_rate(3.0) == _MAX_GROWTH_RATE

    def test_at_cap_unchanged(self):
        assert _clamp_growth_rate(_MAX_GROWTH_RATE) == _MAX_GROWTH_RATE

    def test_custom_floor(self):
        assert _clamp_growth_rate(-0.1, floor=-0.05) == -0.05


# ---------------------------------------------------------------------------
# Issue #431: Owner Earnings must not explode
# ---------------------------------------------------------------------------

class TestOwnerEarningsValuationBounds:
    """The primary fix: growth_rate is clamped inside the function."""

    # Representative OKTA-like financials
    NI = 700_000_000
    DEPR = 100_000_000
    CAPEX = 80_000_000
    WC_CHG = 50_000_000

    def test_reasonable_output_with_normal_growth(self):
        val = calculate_owner_earnings_value(
            self.NI, self.DEPR, self.CAPEX, self.WC_CHG, growth_rate=0.10,
        )
        # Should be in the low tens-of-billions range, not trillions
        assert 1e9 < val < 100e9

    def test_capped_even_with_extreme_growth(self):
        """Before the fix this produced ~$2.6 T with growth_rate=3.0."""
        val = calculate_owner_earnings_value(
            self.NI, self.DEPR, self.CAPEX, self.WC_CHG, growth_rate=3.0,
        )
        # With the cap the output should be identical to growth_rate=0.25
        val_at_cap = calculate_owner_earnings_value(
            self.NI, self.DEPR, self.CAPEX, self.WC_CHG, growth_rate=_MAX_GROWTH_RATE,
        )
        assert val == pytest.approx(val_at_cap)
        # And firmly below $100 B
        assert val < 100e9

    def test_500pct_growth_same_as_capped(self):
        """500 % growth (OKTA-like loss-to-profit) is clamped to cap."""
        val = calculate_owner_earnings_value(
            self.NI, self.DEPR, self.CAPEX, self.WC_CHG, growth_rate=5.0,
        )
        val_cap = calculate_owner_earnings_value(
            self.NI, self.DEPR, self.CAPEX, self.WC_CHG, growth_rate=_MAX_GROWTH_RATE,
        )
        assert val == pytest.approx(val_cap)

    def test_zero_owner_earnings(self):
        val = calculate_owner_earnings_value(0, 0, 100, 0, growth_rate=0.10)
        assert val == 0

    def test_negative_owner_earnings(self):
        val = calculate_owner_earnings_value(100, 0, 200, 0, growth_rate=0.10)
        assert val == 0

    def test_none_inputs(self):
        val = calculate_owner_earnings_value(None, 100, 80, 50, growth_rate=0.10)
        assert val == 0


# ---------------------------------------------------------------------------
# Classic DCF
# ---------------------------------------------------------------------------

class TestIntrinsicValueBounds:
    def test_extreme_growth_clamped(self):
        val = calculate_intrinsic_value(1e9, growth_rate=5.0)
        val_cap = calculate_intrinsic_value(1e9, growth_rate=_MAX_GROWTH_RATE)
        assert val == pytest.approx(val_cap)

    def test_negative_fcf_returns_zero(self):
        assert calculate_intrinsic_value(-100) == 0

    def test_none_fcf_returns_zero(self):
        assert calculate_intrinsic_value(None) == 0


# ---------------------------------------------------------------------------
# Enhanced DCF Scenarios
# ---------------------------------------------------------------------------

class TestDCFScenarios:
    FCF_HIST = [650e6, 500e6, 350e6, 200e6, 100e6]

    def test_bull_wacc_respects_floor(self):
        """Bull WACC (×0.9) must not drop below the 6 % floor."""
        result = calculate_dcf_scenarios(
            fcf_history=self.FCF_HIST,
            growth_metrics={},
            wacc=0.06,  # already at floor
            market_cap=15e9,
            revenue_growth=0.20,
        )
        # Bull scenario's implicit WACC is 0.06 (not 0.054)
        # so bull <= base * some_small_multiplier, not wildly larger
        assert result['upside'] <= result['scenarios']['base'] * 1.5

    def test_extreme_revenue_growth_clamped(self):
        """Revenue growth of 500 % should be clamped before scenarios."""
        result = calculate_dcf_scenarios(
            fcf_history=self.FCF_HIST,
            growth_metrics={},
            wacc=0.10,
            market_cap=15e9,
            revenue_growth=5.0,
        )
        # Expected value should still be in a reasonable range
        assert result['expected_value'] < 200e9  # not trillions

    def test_expected_value_is_weighted_average(self):
        result = calculate_dcf_scenarios(
            fcf_history=self.FCF_HIST,
            growth_metrics={},
            wacc=0.10,
            market_cap=15e9,
            revenue_growth=0.10,
        )
        expected = (
            result['scenarios']['bear'] * 0.2
            + result['scenarios']['base'] * 0.6
            + result['scenarios']['bull'] * 0.2
        )
        assert result['expected_value'] == pytest.approx(expected)

    def test_empty_fcf_returns_zeros(self):
        result = calculate_dcf_scenarios([], {}, 0.10, 15e9, 0.10)
        assert result['expected_value'] == 0


# ---------------------------------------------------------------------------
# WACC
# ---------------------------------------------------------------------------

class TestWACC:
    def test_floor_enforced(self):
        wacc = calculate_wacc(1e12, 0, 1e12, 100, 0)
        assert wacc >= 0.06

    def test_cap_enforced(self):
        wacc = calculate_wacc(1e6, 1e12, 0, 0.1, 100)
        assert wacc <= 0.20

    def test_zero_market_cap_uses_cost_of_equity(self):
        wacc = calculate_wacc(0, 0, 0, None, None)
        # cost_of_equity = 0.045 + 1.0 * 0.06 = 0.105, clamped to [0.06, 0.20]
        assert 0.06 <= wacc <= 0.20


# ---------------------------------------------------------------------------
# FCF Volatility
# ---------------------------------------------------------------------------

class TestFCFVolatility:
    def test_short_history_default(self):
        assert calculate_fcf_volatility([100, 200]) == 0.5

    def test_all_negative_high_volatility(self):
        assert calculate_fcf_volatility([-100, -200, -300]) == 0.8

    def test_stable_fcf_low_volatility(self):
        vol = calculate_fcf_volatility([100, 100, 100, 100])
        assert vol < 0.1


# ---------------------------------------------------------------------------
# Residual Income
# ---------------------------------------------------------------------------

class TestResidualIncomeBounds:
    def test_zero_market_cap_returns_zero(self):
        assert calculate_residual_income_value(0, 1e9, 10) == 0

    def test_negative_ri_returns_zero(self):
        """If net_income < cost_of_equity × book_value, RI is negative → 0."""
        val = calculate_residual_income_value(
            market_cap=100e9, net_income=1e6, price_to_book_ratio=1.0,
        )
        assert val == 0


# ---------------------------------------------------------------------------
# End-to-end: reproduce issue #431 scenario
# ---------------------------------------------------------------------------

class TestIssue431Reproduction:
    """Verify the exact scenario from the bug report cannot recur."""

    def test_okta_like_valuation_under_100B(self):
        """OKTA-like inputs should never produce trillions."""
        # Owner earnings (the main offender)
        oe_val = calculate_owner_earnings_value(
            net_income=700e6,
            depreciation=100e6,
            capex=80e6,
            working_capital_change=50e6,
            growth_rate=5.0,  # 500 % — extreme but plausible for API data
        )

        # DCF scenarios
        dcf = calculate_dcf_scenarios(
            fcf_history=[650e6, 500e6, 350e6, 200e6, 100e6],
            growth_metrics={'revenue_growth': 0.50},
            wacc=0.06,
            market_cap=15e9,
            revenue_growth=5.0,
        )

        # Weighted aggregate (same weights as the agent)
        weighted = (
            dcf['expected_value'] * 0.35
            + oe_val * 0.35
            # omit EV/EBITDA and RIM for simplicity
        )

        # Must be nowhere near $16 T
        assert weighted < 100e9, (
            f"Weighted valuation ${weighted/1e12:.1f}T exceeds $100B — "
            f"growth rate cap is not working"
        )

    def test_all_models_individually_bounded(self):
        """No single model should exceed $500 B for a $15 B company."""
        cap = 500e9

        assert calculate_owner_earnings_value(
            700e6, 100e6, 80e6, 50e6, growth_rate=10.0,
        ) < cap

        assert calculate_intrinsic_value(650e6, growth_rate=10.0) < cap

        dcf = calculate_dcf_scenarios(
            [650e6, 500e6, 350e6], {}, 0.06, 15e9, revenue_growth=10.0,
        )
        assert dcf['upside'] < cap
