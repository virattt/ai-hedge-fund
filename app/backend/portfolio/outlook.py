"""Short-term outlook generation.

Produces probabilistic directional outlooks instead of price predictions.
Combines technical momentum, sentiment, valuation, and volatility signals
into scenario-based intelligence.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ShortTermOutlook:
    """Probabilistic short-term outlook for a holding."""
    direction: str  # "Bullish", "Slightly Bullish", "Neutral", "Slightly Bearish", "Bearish"
    confidence: str  # "Low", "Moderate", "High"
    expected_range_low: float  # e.g. -1.5 (percent)
    expected_range_high: float  # e.g. +3.0 (percent)
    reasoning: list[str] = field(default_factory=list)


def compute_outlook(
    rsi_14: Optional[float] = None,
    trend: Optional[str] = None,
    sentiment: Optional[str] = None,
    valuation_signal: Optional[str] = None,
    annualized_volatility: Optional[float] = None,
    profit_loss_pct: Optional[float] = None,
) -> ShortTermOutlook:
    """Compute a short-term directional outlook from available signals.

    This does NOT predict price. It provides a probabilistic directional
    lean with a confidence-weighted expected movement range.
    """
    # Score: -2 to +2
    direction_score = 0.0
    signal_count = 0
    reasoning: list[str] = []

    # Trend contribution
    if trend == "up":
        direction_score += 1.0
        signal_count += 1
        reasoning.append("Price is above key moving averages (positive momentum)")
    elif trend == "down":
        direction_score -= 1.0
        signal_count += 1
        reasoning.append("Price is below key moving averages (negative momentum)")
    elif trend == "sideways":
        signal_count += 1
        reasoning.append("Price is trading sideways (no clear trend)")

    # RSI contribution
    if rsi_14 is not None:
        signal_count += 1
        if rsi_14 > 70:
            direction_score -= 0.5  # Overbought — likely pullback
            reasoning.append(f"RSI at {rsi_14:.0f} suggests overbought conditions")
        elif rsi_14 > 60:
            direction_score += 0.3
            reasoning.append(f"RSI at {rsi_14:.0f} shows positive momentum")
        elif rsi_14 < 30:
            direction_score += 0.5  # Oversold — likely bounce
            reasoning.append(f"RSI at {rsi_14:.0f} suggests oversold conditions")
        elif rsi_14 < 40:
            direction_score -= 0.3
            reasoning.append(f"RSI at {rsi_14:.0f} shows weak momentum")

    # Sentiment contribution
    if sentiment == "bullish":
        direction_score += 0.5
        signal_count += 1
        reasoning.append("News sentiment is positive")
    elif sentiment == "bearish":
        direction_score -= 0.5
        signal_count += 1
        reasoning.append("News sentiment is negative")
    elif sentiment == "neutral":
        signal_count += 1

    # Valuation contribution (lighter weight for short-term)
    if valuation_signal == "bullish":
        direction_score += 0.3
        signal_count += 1
        reasoning.append("Valuation supports upside potential")
    elif valuation_signal == "bearish":
        direction_score -= 0.3
        signal_count += 1
        reasoning.append("Stretched valuation may cap upside")

    # Determine direction label
    if direction_score >= 1.2:
        direction = "Bullish"
    elif direction_score >= 0.4:
        direction = "Slightly Bullish"
    elif direction_score <= -1.2:
        direction = "Bearish"
    elif direction_score <= -0.4:
        direction = "Slightly Bearish"
    else:
        direction = "Neutral"

    # Confidence based on signal count and agreement
    if signal_count >= 4 and abs(direction_score) >= 1.0:
        confidence = "High"
    elif signal_count >= 2 and abs(direction_score) >= 0.5:
        confidence = "Moderate"
    else:
        confidence = "Low"

    # Expected range based on volatility
    daily_vol = (annualized_volatility / 16.0) if annualized_volatility else 0.015
    # ~1 week outlook (5 days): scale by sqrt(5)
    weekly_vol = daily_vol * 2.24  # sqrt(5)
    weekly_vol_pct = weekly_vol * 100

    # Bias the range based on direction
    if direction_score > 0:
        range_high = round(weekly_vol_pct * (0.8 + direction_score * 0.3), 1)
        range_low = round(-weekly_vol_pct * (0.5 + (1 - direction_score) * 0.2), 1)
    elif direction_score < 0:
        range_high = round(weekly_vol_pct * (0.5 + (1 + direction_score) * 0.2), 1)
        range_low = round(-weekly_vol_pct * (0.8 + abs(direction_score) * 0.3), 1)
    else:
        range_high = round(weekly_vol_pct * 0.7, 1)
        range_low = round(-weekly_vol_pct * 0.7, 1)

    # Add volatility context
    if annualized_volatility:
        if annualized_volatility > 0.4:
            reasoning.append("High volatility increases range of possible outcomes")
        elif annualized_volatility < 0.15:
            reasoning.append("Low volatility suggests narrow trading range")

    return ShortTermOutlook(
        direction=direction,
        confidence=confidence,
        expected_range_low=range_low,
        expected_range_high=range_high,
        reasoning=reasoning,
    )
