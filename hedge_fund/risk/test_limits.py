"""apply_limits tests — pure math."""

import pytest

from hedge_fund.risk.limits import apply_limits, RiskLimits

LIMITS = RiskLimits(max_position_pct=0.25, max_gross_exposure=1.0)


def test_position_clamp_records_event():
    result = apply_limits({"AAPL": 0.6, "MSFT": 0.2}, LIMITS)
    assert result.weights["AAPL"] == pytest.approx(0.25)
    assert result.weights["MSFT"] == pytest.approx(0.2)  # untouched
    assert len(result.clamps) == 1
    clamp = result.clamps[0]
    assert clamp.limit == "max_position_pct"
    assert clamp.ticker == "AAPL"
    assert clamp.before == pytest.approx(0.6)
    assert clamp.after == pytest.approx(0.25)


def test_gross_clamp_scales_all_and_records_one_event():
    limits = RiskLimits(max_position_pct=1.0, max_gross_exposure=1.0)
    result = apply_limits({"AAPL": 0.8, "MSFT": 0.8}, limits)
    assert result.weights["AAPL"] == pytest.approx(0.5)
    assert result.weights["MSFT"] == pytest.approx(0.5)
    assert len(result.clamps) == 1
    assert result.clamps[0].limit == "max_gross_exposure"
    assert result.clamps[0].ticker is None
    assert result.clamps[0].before == pytest.approx(1.6)


def test_position_then_gross_never_reviolates():
    weights = {t: 0.5 for t in ["A", "B", "C", "D", "E", "F"]}  # gross 3.0
    result = apply_limits(weights, LIMITS)
    # Position cap first (0.5 -> 0.25 each, gross 1.5), then gross scale to 1.0.
    for w in result.weights.values():
        assert abs(w) <= LIMITS.max_position_pct + 1e-12
    gross = sum(abs(w) for w in result.weights.values())
    assert gross == pytest.approx(1.0)
    kinds = [c.limit for c in result.clamps]
    assert kinds.count("max_position_pct") == 6
    assert kinds.count("max_gross_exposure") == 1


def test_within_limits_passes_through_untouched():
    weights = {"AAPL": 0.2, "MSFT": -0.1}
    result = apply_limits(weights, LIMITS)
    assert result.weights == weights
    assert result.clamps == []


def test_shorts_clamped_by_absolute_value():
    result = apply_limits({"AAPL": -0.6}, LIMITS)
    assert result.weights["AAPL"] == pytest.approx(-0.25)


def test_clamped_exposure_not_redistributed():
    """Risk only shrinks; freed exposure stays as cash."""
    result = apply_limits({"AAPL": 0.9, "MSFT": 0.05}, LIMITS)
    assert result.weights["AAPL"] == pytest.approx(0.25)
    assert result.weights["MSFT"] == pytest.approx(0.05)  # NOT topped up


def test_proportional_position_cap_preserves_neutrality():
    result = apply_limits({"A": .5, "B": -.25, "C": -.25}, LIMITS, preserve_proportions=True)
    assert result.weights == {"A": .25, "B": -.125, "C": -.125}
    assert result.scale_factor == .5
    assert [(c.ticker, c.before, c.after) for c in result.clamps] == [("A", .5, .25)]


def test_proportional_position_and_gross_caps_compose():
    limits = RiskLimits(max_position_pct=.25, max_gross_exposure=.3)
    result = apply_limits({"A": .5, "B": -.25, "C": -.25}, limits, preserve_proportions=True)
    assert result.weights == pytest.approx({"A": .15, "B": -.075, "C": -.075})
    assert result.scale_factor == pytest.approx(.3)
    assert [c.limit for c in result.clamps] == ["max_position_pct", "max_gross_exposure"]
    again = apply_limits(result.weights, limits, preserve_proportions=True)
    assert again.weights == result.weights
    assert again.scale_factor == 1


@pytest.mark.parametrize("weights", [{}, {"A": 0}, {"A": .1, "B": -.1}])
def test_proportional_within_limits_is_unchanged(weights):
    result = apply_limits(weights, LIMITS, preserve_proportions=True)
    assert result.weights == weights
    assert result.scale_factor == 1
    assert result.clamps == []


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("proportional", [False, True])
def test_nonfinite_weights_fail_before_risk_adjustment(value, proportional):
    with pytest.raises(ValueError, match="A.*finite"):
        apply_limits({"A": value}, LIMITS, preserve_proportions=proportional)
