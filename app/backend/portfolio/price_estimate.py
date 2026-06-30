"""Experimental next-session price estimate.

EDUCATIONAL ONLY — NOT FINANCIAL ADVICE.

Computes a probabilistic next-day price estimate using:
- Current price
- Recent daily volatility
- 5-day momentum (clipped)
- 20-day trend score
- Sentiment score
- Agent consensus score

Never claims certainty. Always labelled as experimental.
"""

from dataclasses import dataclass
from typing import Optional

import logging

logger = logging.getLogger(__name__)


@dataclass
class PriceEstimate:
    """Experimental next-session price estimate."""
    estimated_next_price: float
    expected_low: float
    expected_high: float
    estimate_confidence: str  # "Low", "Moderate", "High"
    estimate_reason: str


def compute_price_estimate(
    current_price: float,
    daily_returns: Optional[list[float]] = None,
    sentiment_score: Optional[float] = None,
    agent_consensus_score: Optional[float] = None,
    is_etf: bool = False,
    ticker: str = "",
) -> Optional[PriceEstimate]:
    """Compute experimental next-session price estimate.

    Args:
        current_price: Latest close price.
        daily_returns: List of recent daily returns (newest last). Needs at least 5.
        sentiment_score: -1.0 (bearish) to +1.0 (bullish). None if unavailable.
        agent_consensus_score: -1.0 (bearish) to +1.0 (bullish). None if unavailable.
        is_etf: Whether this is an ETF/fund (tighter movement caps).
        ticker: Ticker symbol for logging.

    Returns:
        PriceEstimate or None if insufficient data.
    """
    if current_price <= 0:
        return None

    if not daily_returns or len(daily_returns) < 5:
        return None

    # --- Compute inputs ---

    # Daily volatility (std of recent returns)
    recent_returns = daily_returns[-20:] if len(daily_returns) >= 20 else daily_returns
    n = len(recent_returns)
    mean_ret = sum(recent_returns) / n
    variance = sum((r - mean_ret) ** 2 for r in recent_returns) / max(n - 1, 1)
    daily_volatility = variance ** 0.5

    if daily_volatility <= 0:
        daily_volatility = 0.01  # Minimum floor

    # 5-day momentum: average of last 5 returns, clipped
    last_5 = daily_returns[-5:]
    raw_5d_return = sum(last_5) / len(last_5)
    # Clip to ±3% per day on average
    clipped_5d_return = max(-0.03, min(0.03, raw_5d_return))

    # 20-day trend score: proportion of positive days - 0.5, scaled to [-1, 1]
    last_20 = daily_returns[-20:] if len(daily_returns) >= 20 else daily_returns
    positive_days = sum(1 for r in last_20 if r > 0)
    trend_score = (positive_days / len(last_20) - 0.5) * 2  # -1 to +1

    # --- Apply formula ---
    base = current_price

    momentum_adjustment = current_price * clipped_5d_return * 0.35
    trend_adjustment = current_price * trend_score * 0.01

    sentiment_adjustment = 0.0
    if sentiment_score is not None:
        sentiment_adjustment = current_price * sentiment_score * 0.005

    agent_adjustment = 0.0
    if agent_consensus_score is not None:
        agent_adjustment = current_price * agent_consensus_score * 0.0075

    estimated_next_price = (
        base + momentum_adjustment + trend_adjustment
        + sentiment_adjustment + agent_adjustment
    )

    # --- Apply movement caps ---
    if is_etf:
        max_move_pct = 0.02  # ±2% for ETFs/funds
    elif daily_volatility > 0.04:
        max_move_pct = 0.08  # ±8% for high-vol stocks
    else:
        max_move_pct = 0.05  # ±5% for normal equities

    max_move = current_price * max_move_pct
    estimated_next_price = max(
        current_price - max_move,
        min(current_price + max_move, estimated_next_price)
    )

    # --- Compute range ---
    expected_low = estimated_next_price - daily_volatility * current_price
    expected_high = estimated_next_price + daily_volatility * current_price

    # Ensure range doesn't exceed caps
    expected_low = max(current_price * (1 - max_move_pct), expected_low)
    expected_high = min(current_price * (1 + max_move_pct), expected_high)

    # --- Confidence ---
    has_price = True
    has_volatility = daily_volatility > 0
    has_sentiment = sentiment_score is not None
    has_agents = agent_consensus_score is not None

    # Check agent agreement (strong consensus = magnitude > 0.5)
    agents_agree = has_agents and abs(agent_consensus_score) > 0.3

    if has_price and has_volatility and has_sentiment and agents_agree:
        confidence = "High"
    elif has_price and has_volatility and (has_sentiment or has_agents):
        confidence = "Moderate"
    else:
        confidence = "Low"

    # --- Reason ---
    factors = []
    if abs(clipped_5d_return) > 0.005:
        direction = "positive" if clipped_5d_return > 0 else "negative"
        factors.append(f"5-day momentum is {direction}")
    if abs(trend_score) > 0.2:
        direction = "upward" if trend_score > 0 else "downward"
        factors.append(f"20-day trend is {direction}")
    if has_sentiment and abs(sentiment_score) > 0.2:
        direction = "positive" if sentiment_score > 0 else "negative"
        factors.append(f"sentiment is {direction}")
    if has_agents and abs(agent_consensus_score) > 0.2:
        direction = "positive" if agent_consensus_score > 0 else "negative"
        factors.append(f"agent consensus is {direction}")

    if factors:
        reason = "Experimental estimate based on " + ", ".join(factors) + "."
    else:
        reason = "Experimental estimate based on recent price action and volatility."

    return PriceEstimate(
        estimated_next_price=round(estimated_next_price, 4),
        expected_low=round(expected_low, 4),
        expected_high=round(expected_high, 4),
        estimate_confidence=confidence,
        estimate_reason=reason,
    )


def estimate_to_dict(estimate: Optional[PriceEstimate]) -> Optional[dict]:
    """Convert PriceEstimate to a JSON-serializable dict."""
    if estimate is None:
        return None
    return {
        "estimated_next_price": estimate.estimated_next_price,
        "expected_low": estimate.expected_low,
        "expected_high": estimate.expected_high,
        "estimate_confidence": estimate.estimate_confidence,
        "estimate_reason": estimate.estimate_reason,
    }
