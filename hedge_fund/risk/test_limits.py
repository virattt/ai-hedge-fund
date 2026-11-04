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


# ---------------------------------------------------------------------------
# Net exposure band
# ---------------------------------------------------------------------------

def test_net_clamp_scales_only_the_heavier_side():
    limits = RiskLimits(max_position_pct=1.0, max_gross_exposure=2.0, max_net_exposure=0.2)
    result = apply_limits({"A": 0.5, "B": 0.3, "C": -0.2}, limits)   # net +0.6
    # Longs scaled by (0.2 + 0.2) / 0.8 = 0.5; the short is untouched.
    assert result.weights == pytest.approx({"A": 0.25, "B": 0.15, "C": -0.2})
    assert sum(result.weights.values()) == pytest.approx(0.2)
    assert [c.limit for c in result.clamps] == ["max_net_exposure"]
    assert result.clamps[0].ticker is None
    assert (result.clamps[0].before, result.clamps[0].after) == (pytest.approx(0.6), pytest.approx(0.2))


def test_net_clamp_mirrors_for_a_short_heavy_book():
    limits = RiskLimits(max_position_pct=1.0, max_gross_exposure=2.0, max_net_exposure=0.1)
    result = apply_limits({"A": 0.2, "B": -0.5, "C": -0.3}, limits)   # net -0.6
    # Shorts scaled by (0.1 + 0.2) / 0.8 = 0.375.
    assert result.weights == pytest.approx({"A": 0.2, "B": -0.1875, "C": -0.1125})
    assert sum(result.weights.values()) == pytest.approx(-0.1)
    assert result.clamps[0].after == pytest.approx(-0.1)


def test_net_within_the_band_or_unset_passes_through():
    banded = RiskLimits(max_position_pct=1.0, max_gross_exposure=2.0, max_net_exposure=0.5)
    assert apply_limits({"A": 0.4, "B": -0.1}, banded).clamps == []
    assert apply_limits({"A": 0.9, "B": 0.9}, RiskLimits(max_position_pct=1.0, max_gross_exposure=2.0)).clamps == []


def test_net_then_gross_compose_and_never_reviolate():
    limits = RiskLimits(max_position_pct=1.0, max_gross_exposure=0.8, max_net_exposure=0.2)
    result = apply_limits({"A": 1.0, "B": 0.6, "C": -0.4}, limits)   # net 1.2, gross 2.0
    # Net first: longs x 0.375 -> A .375, B .225, C -.4 (gross 1.0); then gross x 0.8.
    assert result.weights == pytest.approx({"A": 0.3, "B": 0.18, "C": -0.32})
    assert sum(result.weights.values()) <= 0.2 + 1e-12
    assert sum(abs(w) for w in result.weights.values()) == pytest.approx(0.8)
    assert [c.limit for c in result.clamps] == ["max_net_exposure", "max_gross_exposure"]


def test_proportional_net_clamp_keeps_neutrality_and_reports_the_factor():
    limits = RiskLimits(max_position_pct=1.0, max_gross_exposure=2.0, max_net_exposure=0.1)
    result = apply_limits({"A": 0.5, "B": -0.3}, limits, preserve_proportions=True)   # net 0.2
    assert result.weights == pytest.approx({"A": 0.25, "B": -0.15})
    assert result.scale_factor == pytest.approx(0.5)
    assert [c.limit for c in result.clamps] == ["max_net_exposure"]


# ---------------------------------------------------------------------------
# The whole-book scalers: sector, beta, volatility, the drawdown halving
# ---------------------------------------------------------------------------

from hedge_fund.risk.exposures import Exposures, NameExposure  # noqa: E402

WIDE = dict(max_position_pct=1.0, max_gross_exposure=1.0)


def _model(**names):
    """beta, residual vol, sector per name; benchmark vol 0.2."""
    return Exposures(as_of="2024-06-03", benchmark_volatility=0.2, names={
        t: NameExposure(beta=b, residual_volatility=r, sector=s, n_bars=250) for t, (b, r, s) in names.items()
    })


def test_sector_cap_scales_the_whole_book_and_names_the_sector():
    model = _model(A=(1, 0, "Tech"), B=(1, 0, "Tech"), C=(1, 0, "Energy"), D=(1, 0, None))
    result = apply_limits({"A": 0.4, "B": 0.2, "C": -0.1, "D": 0.2}, RiskLimits(**WIDE, max_sector_pct=0.3),
                          exposures=model)
    assert result.weights == {"A": pytest.approx(0.2), "B": pytest.approx(0.1),
                              "C": pytest.approx(-0.05), "D": pytest.approx(0.1)}
    assert [(c.limit, c.ticker, c.sector, c.before, c.after) for c in result.clamps] == [
        ("max_sector_pct", None, "Tech", pytest.approx(0.6), pytest.approx(0.3))]


@pytest.mark.parametrize("sign", [1, -1])
def test_beta_cap_scales_the_book_to_the_signed_cap(sign):
    result = apply_limits({"A": sign * 0.4}, RiskLimits(**WIDE, max_beta=0.5), exposures=_model(A=(2.0, 0, None)))
    assert result.weights["A"] == pytest.approx(sign * 0.25)
    assert [(c.limit, c.before, c.after) for c in result.clamps] == [
        ("max_beta", pytest.approx(sign * 0.8), pytest.approx(sign * 0.5))]


def test_volatility_cap_scales_the_book_to_the_cap():
    result = apply_limits({"A": 1.0}, RiskLimits(**WIDE, max_volatility=0.1), exposures=_model(A=(1.0, 0, None)))
    assert result.weights["A"] == pytest.approx(0.5)
    assert [(c.limit, c.before, c.after) for c in result.clamps] == [
        ("max_volatility", pytest.approx(0.2), pytest.approx(0.1))]


def test_the_halving_tier_fires_at_the_line_and_not_under_it():
    limits = RiskLimits(**WIDE, halve_drawdown_pct=0.10, max_drawdown_pct=0.20)
    halved = apply_limits({"A": 0.8, "B": -0.2}, limits, drawdown=0.10)
    assert halved.weights == {"A": pytest.approx(0.4), "B": pytest.approx(-0.1)}
    assert [(c.limit, c.before, c.after) for c in halved.clamps] == [("halve_drawdown_pct", 0.10, 0.5)]
    assert apply_limits({"A": 0.8, "B": -0.2}, limits, drawdown=0.0999).clamps == []


def test_a_halved_book_under_the_gross_cap_records_no_gross_clamp():
    result = apply_limits({"A": 0.8, "B": 0.8}, RiskLimits(**WIDE, halve_drawdown_pct=0.10), drawdown=0.15)
    assert result.weights == {"A": pytest.approx(0.4), "B": pytest.approx(0.4)}
    assert [c.limit for c in result.clamps] == ["halve_drawdown_pct"]


def test_the_proportional_path_folds_every_book_factor_into_the_scale_factor():
    limits = RiskLimits(**WIDE, max_beta=0.5, halve_drawdown_pct=0.10)
    result = apply_limits({"A": 0.4, "B": -0.4}, limits, preserve_proportions=True, drawdown=0.12,
                          exposures=_model(A=(2.0, 0, None), B=(0.5, 0, None)))
    factor = (0.5 / 0.6) * 0.5
    assert result.scale_factor == pytest.approx(factor)
    assert result.weights == {"A": pytest.approx(0.4 * factor), "B": pytest.approx(-0.4 * factor)}
    assert sum(result.weights.values()) == pytest.approx(0.0)
    assert [c.limit for c in result.clamps] == ["max_beta", "halve_drawdown_pct"]


def test_a_factor_cap_needs_exposures_for_every_name():
    with pytest.raises(ValueError, match="needs the book's exposures"):
        apply_limits({"A": 0.1}, RiskLimits(**WIDE, max_beta=0.5))
    with pytest.raises(ValueError, match="no exposure for B"):
        apply_limits({"A": 0.1, "B": 0.1}, RiskLimits(**WIDE, max_beta=0.5), exposures=_model(A=(1, 0, None)))
    with pytest.raises(ValueError, match="drawdown"):
        apply_limits({"A": 0.1}, RiskLimits(**WIDE), drawdown=-0.1)
