"""apply_limits tests — pure math."""

import pytest

from hedge_fund.risk.limits import RiskLimits, apply_limits

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


# --- cash reserve floor: a cap on NET exposure ------------------------------

RESERVE = RiskLimits(
    max_position_pct=1.0, max_gross_exposure=2.0, min_cash_reserve_pct=0.10
)


def test_no_floor_by_default_even_when_fully_invested():
    """The default of 0.0 must not perturb a book that sits at net 1.0."""
    limits = RiskLimits(max_position_pct=1.0, max_gross_exposure=2.0)
    weights = {"AAPL": 0.6, "MSFT": 0.4}
    result = apply_limits(weights, limits)
    assert result.weights == weights
    assert result.clamps == []


def test_net_exposure_clamped_to_the_ceiling():
    result = apply_limits({"AAPL": 0.6, "MSFT": 0.4}, RESERVE)
    assert sum(result.weights.values()) == pytest.approx(0.9)
    assert result.weights["AAPL"] == pytest.approx(0.54)
    assert result.weights["MSFT"] == pytest.approx(0.36)
    assert len(result.clamps) == 1
    clamp = result.clamps[0]
    assert clamp.limit == "min_cash_reserve_pct"
    assert clamp.ticker is None
    assert clamp.before == pytest.approx(1.0)
    assert clamp.after == pytest.approx(0.9)


def test_market_neutral_book_is_left_alone():
    """Net ~0 already holds ~100% cash; a reserve has nothing to reclaim."""
    weights = {"AAPL": 0.5, "MSFT": -0.5}
    result = apply_limits(weights, RESERVE)
    assert result.weights == weights
    assert result.clamps == []


def test_net_short_book_is_left_alone():
    weights = {"AAPL": 0.2, "MSFT": -0.5}
    result = apply_limits(weights, RESERVE)
    assert result.weights == weights
    assert result.clamps == []


def test_shorts_shrink_alongside_longs():
    """Scaling is proportional across the whole book, not longs-only."""
    result = apply_limits({"AAPL": 0.8, "MSFT": 0.6, "TSLA": -0.2}, RESERVE)
    assert sum(result.weights.values()) == pytest.approx(0.9)
    scale = 0.9 / 1.2
    assert result.weights["AAPL"] == pytest.approx(0.8 * scale)
    assert result.weights["MSFT"] == pytest.approx(0.6 * scale)
    assert result.weights["TSLA"] == pytest.approx(-0.2 * scale)


def test_floor_runs_last_and_reviolates_nothing():
    limits = RiskLimits(
        max_position_pct=0.25, max_gross_exposure=1.0, min_cash_reserve_pct=0.10
    )
    weights = {t: 0.5 for t in ["A", "B", "C", "D", "E", "F"]}
    result = apply_limits(weights, limits)
    for w in result.weights.values():
        assert abs(w) <= limits.max_position_pct + 1e-12
    assert sum(abs(w) for w in result.weights.values()) <= 1.0 + 1e-12
    assert sum(result.weights.values()) == pytest.approx(0.9)
    kinds = [c.limit for c in result.clamps]
    assert kinds == ["max_position_pct"] * 6 + [
        "max_gross_exposure", "min_cash_reserve_pct",
    ]


def test_floor_is_idempotent():
    once = apply_limits({"AAPL": 0.6, "MSFT": 0.4}, RESERVE)
    twice = apply_limits(once.weights, RESERVE)
    assert twice.weights == once.weights
    assert twice.clamps == []
