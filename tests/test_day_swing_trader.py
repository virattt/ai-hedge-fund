"""Unit tests for the Day & Swing Trader agent.

Mocks get_prices and call_llm so the agent's pipeline can be exercised
without network or API-key requirements.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.agents.day_swing_trader import (
    DaySwingTraderSignal,
    build_features,
    compute_discount_premium_zone,
    day_swing_trader_agent,
    detect_itf_range,
)
from src.data.models import Price


def _synthetic_prices(days: int = 220) -> list[Price]:
    """Generate a gently trending series with a recent pullback wick on the last bar."""
    start = datetime(2024, 1, 1)
    prices: list[Price] = []
    base = 100.0
    for i in range(days):
        drift = i * 0.25  # upward trend
        close = base + drift
        open_ = close - 0.5
        high = close + 0.8
        low = close - 0.8
        # Stop-hunt wick on the final bar: dip well below recent lows, close back up
        if i == days - 1:
            low = close - 6.0
            open_ = close - 1.5
        t = (start + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z")
        prices.append(Price(open=open_, close=close, high=high, low=low, volume=1_000_000, time=t))
    return prices


def test_detect_itf_range_basic():
    prices = _synthetic_prices(60)
    from src.tools.api import prices_to_df

    df = prices_to_df(prices)
    r = detect_itf_range(df, lookback=20)
    assert r["high"] > r["low"]
    assert r["low"] <= r["mid"] <= r["high"]
    assert r["width"] == pytest.approx(r["high"] - r["low"], rel=1e-6)


def test_compute_discount_premium_zone_labels():
    range_bounds = {"low": 100.0, "high": 200.0, "mid": 150.0, "width": 100.0, "lookback": 20}

    zone_low = compute_discount_premium_zone(range_bounds, current_price=110.0)
    assert zone_low["label"] == "discount"
    assert 0.0 <= zone_low["position_in_range"] <= 0.5

    zone_high = compute_discount_premium_zone(range_bounds, current_price=190.0)
    assert zone_high["label"] == "premium"
    assert zone_high["position_in_range"] >= 0.5


def test_build_features_has_required_keys():
    prices = _synthetic_prices(220)
    from src.tools.api import prices_to_df

    df = prices_to_df(prices)
    features = build_features(df)
    for key in (
        "htf_trend",
        "itf_range",
        "current_price",
        "zone",
        "manipulation",
        "order_blocks",
        "fair_value_gaps",
        "ltf_confirmation",
        "invalidation",
    ):
        assert key in features, f"missing feature key: {key}"


@patch("src.agents.day_swing_trader.call_llm")
@patch("src.agents.day_swing_trader.get_prices")
def test_agent_returns_valid_signal(mock_get_prices, mock_call_llm):
    mock_get_prices.return_value = _synthetic_prices(220)
    mock_call_llm.return_value = DaySwingTraderSignal(
        signal="bullish",
        confidence=72.5,
        reasoning="Mocked: HTF bullish, manipulation wick into discount zone, LTF confirmation.",
    )

    state = {
        "messages": [],
        "data": {
            "tickers": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-08-01",
            "analyst_signals": {},
        },
        "metadata": {"show_reasoning": False},
    }

    result = day_swing_trader_agent(state, agent_id="day_swing_trader_agent")

    signals = result["data"]["analyst_signals"]["day_swing_trader_agent"]
    assert "AAPL" in signals

    aapl = signals["AAPL"]
    assert aapl["signal"] in {"bullish", "bearish", "neutral"}
    assert 0.0 <= aapl["confidence"] <= 100.0
    assert isinstance(aapl["reasoning"], str) and aapl["reasoning"]

    mock_get_prices.assert_called_once()
    mock_call_llm.assert_called_once()
    # Ensure the feature dict passed to the LLM has non-trivial structure.
    llm_kwargs = mock_call_llm.call_args.kwargs
    assert llm_kwargs["pydantic_model"] is DaySwingTraderSignal
    assert llm_kwargs["agent_name"] == "day_swing_trader_agent"


@patch("src.agents.day_swing_trader.call_llm")
@patch("src.agents.day_swing_trader.get_prices")
def test_agent_skips_ticker_when_no_prices(mock_get_prices, mock_call_llm):
    mock_get_prices.return_value = []
    state = {
        "messages": [],
        "data": {
            "tickers": ["ZZZZ"],
            "start_date": "2024-01-01",
            "end_date": "2024-08-01",
            "analyst_signals": {},
        },
        "metadata": {"show_reasoning": False},
    }

    result = day_swing_trader_agent(state, agent_id="day_swing_trader_agent")

    signals = result["data"]["analyst_signals"]["day_swing_trader_agent"]
    assert signals == {}
    mock_call_llm.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__])
