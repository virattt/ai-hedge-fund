"""blend_signals tests — pure math, hand-built signals."""

import pytest

from v2.models import Signal
from v2.portfolio.construction import blend_signals


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


def test_all_abstain_yields_flat_book():
    signals = [
        _sig("a", "AAPL", 0.0, abstained=True),
        _sig("b", "AAPL", 0.0, abstained=True),
    ]
    result = blend_signals(signals, {"a": 1.0, "b": 1.0}, gross_target=1.0)
    assert result.convictions == {"AAPL": 0.0}
    assert result.weights == {"AAPL": 0.0}
