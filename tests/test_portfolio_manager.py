import pytest
from src.agents.portfolio_manager import aggregate_signals, scale_quantity_by_confidence


def test_high_confidence_bullish_wins():
    signals = {
        "agent_a": {"sig": "bullish", "conf": 90},
        "agent_b": {"sig": "bearish", "conf": 30},
    }
    result = aggregate_signals(signals)
    assert result["signal"] == "bullish"
    assert result["confidence"] > 50


def test_high_confidence_bearish_wins():
    signals = {
        "agent_a": {"sig": "bearish", "conf": 85},
        "agent_b": {"sig": "bullish", "conf": 40},
    }
    result = aggregate_signals(signals)
    assert result["signal"] == "bearish"


def test_balanced_confidence_returns_neutral():
    signals = {
        "agent_a": {"sig": "bullish", "conf": 60},
        "agent_b": {"sig": "bearish", "conf": 60},
    }
    result = aggregate_signals(signals)
    assert result["signal"] == "neutral"


def test_neutral_signal_contributes_zero():
    signals = {
        "agent_a": {"sig": "bullish", "conf": 70},
        "agent_b": {"sig": "neutral", "conf": 100},
    }
    result = aggregate_signals(signals)
    assert result["signal"] == "bullish"


def test_empty_signals_returns_neutral_zero_confidence():
    result = aggregate_signals({})
    assert result["signal"] == "neutral"
    assert result["confidence"] == 0


def test_single_bullish_agent():
    signals = {"only_agent": {"sig": "bullish", "conf": 80}}
    result = aggregate_signals(signals)
    assert result["signal"] == "bullish"
    assert result["confidence"] == 80


def test_confidence_is_int_between_0_and_100():
    signals = {
        "a": {"sig": "bullish", "conf": 75},
        "b": {"sig": "bullish", "conf": 55},
    }
    result = aggregate_signals(signals)
    assert isinstance(result["confidence"], int)
    assert 0 <= result["confidence"] <= 100


def test_result_has_required_keys():
    result = aggregate_signals({"a": {"sig": "bullish", "conf": 60}})
    assert "signal" in result
    assert "confidence" in result
    assert "weighted_score" in result


def test_scale_quantity_full_confidence():
    assert scale_quantity_by_confidence(100, 100) == 100


def test_scale_quantity_zero_quantity():
    assert scale_quantity_by_confidence(0, 80) == 0


def test_scale_quantity_zero_confidence_returns_zero():
    result = scale_quantity_by_confidence(10, 0)
    assert result == 0


def test_scale_quantity_proportional():
    # 50% confidence should give ~50% of 100 shares
    result = scale_quantity_by_confidence(100, 50)
    assert result == 50
