"""blend_signals tests — pure math, hand-built signals."""

import pytest

from hedge_fund.models import Signal
from hedge_fund.portfolio.construction import blend_signals as _blend_signals


def blend_signals(signals, model_weights, gross_target, *, mode="long_short", investment_approaches=None):
    return _blend_signals(signals, model_weights, gross_target, mode=mode,
                          investment_approaches=investment_approaches or {m: "long_short" for m in model_weights})


def _sig(model, ticker, value, abstained=False):
    metadata = {"abstained": True} if abstained else {}
    return Signal(model_name=model, ticker=ticker, date="2024-06-03",
                  value=value, metadata=metadata)


def test_weighted_mean_with_unequal_weights():
    signals = [_sig("a", "AAPL", 1.0), _sig("b", "AAPL", 0.0)]
    result = blend_signals(signals, {"a": 3.0, "b": 1.0}, gross_target=1.0)
    assert result.convictions["AAPL"] == pytest.approx(0.75)  # (3*1 + 1*0) / 4


def test_abstain_excluded_from_denominator():
    """bullish + abstain must blend to fully bullish, not half."""
    signals = [_sig("a", "AAPL", 1.0), _sig("b", "AAPL", 0.0, abstained=True)]
    result = blend_signals(signals, {"a": 1.0, "b": 1.0}, gross_target=1.0)
    assert result.convictions["AAPL"] == pytest.approx(1.0)


def test_non_abstained_zero_dilutes():
    """A real neutral vote (e.g. PEAD outside its window) is a vote."""
    signals = [_sig("a", "AAPL", 1.0), _sig("b", "AAPL", 0.0)]
    result = blend_signals(signals, {"a": 1.0, "b": 1.0}, gross_target=1.0)
    assert result.convictions["AAPL"] == pytest.approx(0.5)


def test_weights_sum_to_gross_target():
    signals = [
        _sig("a", "AAPL", 0.8),
        _sig("a", "MSFT", -0.4),
        _sig("a", "NVDA", 0.2),
    ]
    result = blend_signals(signals, {"a": 1.0}, gross_target=1.0)
    gross = sum(abs(w) for w in result.weights.values())
    assert gross == pytest.approx(1.0)
    assert result.weights["MSFT"] < 0  # bearish view -> negative weight


def test_dollar_neutral_sleeve_sums_to_zero():
    signals = [
        _sig("a", "AAPL", 1.0),
        _sig("a", "MSFT", 0.2),
        _sig("a", "NVDA", -0.6),
    ]
    result = blend_signals(signals, {"a": 1.0}, gross_target=1.0, mode="dollar_neutral")
    assert sum(result.weights.values()) == pytest.approx(0.0)  # dollar-neutral
    assert sum(abs(w) for w in result.weights.values()) == pytest.approx(1.0)
    # Only explicitly bearish evidence supports the short side.
    assert result.weights["AAPL"] > 0 > result.weights["NVDA"]
    assert result.weights["MSFT"] > 0
    # Raw opinions are retained alongside the eligible sizing scores.
    assert result.convictions["MSFT"] == pytest.approx(0.2)


def test_dollar_neutral_all_positive_views_go_flat():
    """Bullish opinions cannot be converted into shorts to force neutrality."""
    signals = [_sig("a", t, 0.8) for t in ("AAPL", "MSFT", "NVDA")]
    result = blend_signals(signals, {"a": 1.0}, gross_target=1.0, mode="dollar_neutral")
    assert all(w == 0.0 for w in result.weights.values())


def test_all_abstain_yields_flat_book():
    signals = [
        _sig("a", "AAPL", 0.0, abstained=True),
        _sig("b", "AAPL", 0.0, abstained=True),
    ]
    result = blend_signals(signals, {"a": 1.0, "b": 1.0}, gross_target=1.0)
    assert result.convictions == {"AAPL": 0.0}
    assert result.weights == {"AAPL": 0.0}


@pytest.mark.parametrize("bull,bear,expected", [(.8, -.6, .1), (-.8, .6, 0), (-.8, -.6, -.3), (-.8, 0, 0)])
def test_mixed_opinions_respect_analyst_permissions(bull, bear, expected):
    result = blend_signals([_sig("owner", "A", bull), _sig("trader", "A", bear)],
                          {"owner": 1, "trader": 1}, 1,
                          investment_approaches={"owner": "long_only", "trader": "long_short"})
    assert result.convictions["A"] == pytest.approx((bull + bear) / 2)
    assert result.eligible_scores["A"] == pytest.approx(expected)
    assert result.weights["A"] == pytest.approx(0 if expected == 0 else 1 if expected > 0 else -1)


@pytest.mark.parametrize("owner_value", [-1, -.5, 0])
def test_long_only_bearishness_never_strengthens_short(owner_value):
    result = blend_signals([_sig("owner", "A", owner_value), _sig("trader", "A", -.6)],
                          {"owner": 3, "trader": 1}, 1,
                          investment_approaches={"owner": "long_only", "trader": "long_short"})
    assert result.eligible_scores["A"] == pytest.approx(-.15)


@pytest.mark.parametrize("abstained,expected", [(False, -.15), (True, -.6)])
def test_mixed_abstention_and_neutral_vote_use_same_denominator(abstained, expected):
    result = blend_signals([_sig("owner", "A", 0, abstained), _sig("trader", "A", -.6)],
                          {"owner": 3, "trader": 1}, 1,
                          investment_approaches={"owner": "long_only", "trader": "long_short"})
    assert result.eligible_scores["A"] == pytest.approx(expected)


def test_long_only_ignores_negative_targets_even_from_short_capable_analyst():
    result = blend_signals([_sig("a", "A", .5), _sig("a", "B", -.8)], {"a": 1}, 1, mode="long_only")
    assert result.weights == {"A": 1, "B": 0}
    assert result.convictions["B"] == -.8
    assert result.eligible_scores["B"] == 0


@pytest.mark.parametrize("values,reason", [([.8, .2], "missing_short_side"), ([-.8, -.2], "missing_long_side"), ([0, 0], "no_eligible_positions"), ([1e-10, -1e-10], "no_eligible_positions")])
def test_neutral_missing_sides_are_explained(values, reason):
    result = blend_signals([_sig("a", t, v) for t, v in zip(["A", "B"], values)], {"a": 1}, 1, mode="dollar_neutral")
    assert result.weights == {"A": 0, "B": 0}
    assert result.flat_reason == reason


def test_asymmetric_neutral_scores_allocate_half_to_each_side():
    result = blend_signals([_sig("a", "A", 1), _sig("a", "B", -.1), _sig("a", "C", -.3)], {"a": 1}, 1.6, mode="dollar_neutral")
    assert result.weights == pytest.approx({"A": .8, "B": -.2, "C": -.6})
    assert result.flat_reason is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 1.1, -1.1])
@pytest.mark.parametrize("abstained", [False, True])
def test_invalid_signal_is_rejected(value, abstained):
    with pytest.raises(ValueError, match="A.*a.*finite"):
        blend_signals([_sig("a", "A", value, abstained)], {"a": 1}, 1)


@pytest.mark.parametrize("weight", [0, -1, float("nan"), float("inf")])
def test_invalid_model_weight_is_rejected(weight):
    with pytest.raises(ValueError, match="a.*weight"):
        blend_signals([], {"a": weight}, 1)


@pytest.mark.parametrize("gross", [0, -1, float("nan"), float("inf")])
def test_invalid_gross_target_is_rejected(gross):
    with pytest.raises(ValueError, match="gross_target"):
        blend_signals([], {"a": 1}, gross)


def test_unknown_mode_or_missing_profile_is_rejected():
    with pytest.raises(ValueError, match="mode"):
        blend_signals([], {"a": 1}, 1, mode="invalid")
    for approaches in ({}, {"a": "invalid"}):
        with pytest.raises(ValueError, match="a.*approach"):
            _blend_signals([], {"a": 1}, 1, mode="long_short", investment_approaches=approaches)
    with pytest.raises(ValueError, match="no blend weight"):
        blend_signals([_sig("unknown", "A", 1)], {"a": 1}, 1)


def test_signal_accumulation_overflow_is_rejected():
    with pytest.raises(ValueError, match="totals must be finite"):
        blend_signals([_sig("a", "A", 1), _sig("b", "A", 1)], {"a": 1e308, "b": 1e308}, 1)
