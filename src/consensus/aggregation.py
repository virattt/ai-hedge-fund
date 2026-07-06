"""Deterministic consensus aggregation strategies for multi-agent signals.

No LLM calls — pure computation. Three strategies supported:
- weighted: signal × confidence weighted average
- majority: count-based voting (bullish/bearish/neutral)
- mean: simple arithmetic mean of numeric signal values
"""

from collections import Counter
from typing import Optional

from src.consensus.models import (
    AgentContribution,
    ConsensusSignal,
    ConsensusResult,
)

# Thresholds
NEUTRAL_DEADBAND: float = 0.2  # Scores in (-0.2, +0.2) are treated as neutral
OUTLIER_STDDEV_MULTIPLIER: float = 1.5  # Signals beyond this many stddevs from mean are outliers


def _signal_to_numeric(signal: str) -> float:
    """Convert signal string to numeric value."""
    signal_lower = signal.lower()
    if signal_lower == "bullish":
        return 1.0
    elif signal_lower == "bearish":
        return -1.0
    else:
        return 0.0


def _numeric_to_signal(score: float) -> str:
    """Convert numeric score back to signal string."""
    if score > NEUTRAL_DEADBAND:
        return "bullish"
    elif score < -NEUTRAL_DEADBAND:
        return "bearish"
    return "neutral"


def aggregate_signals(
    contributions: list[AgentContribution],
    strategy: str = "weighted",
    weights: Optional[dict[str, float]] = None,
) -> ConsensusSignal:
    """Aggregate multiple agent signals into a single consensus.

    Args:
        contributions: List of agent contributions (signal + confidence + reasoning)
        strategy: Aggregation strategy — 'weighted', 'majority', or 'mean'
        weights: Optional per-agent weight multipliers (default 1.0 for all)

    Returns:
        ConsensusSignal with composite score, confidence, agreement, and outliers.
    """
    if not contributions:
        raise ValueError("At least one agent contribution is required")

    if weights is None:
        weights = {}

    # Compute composite score based on strategy
    if strategy == "majority":
        score = _aggregate_majority(contributions, weights)
    elif strategy == "mean":
        score = _aggregate_mean(contributions)
    else:  # weighted (default)
        score = _aggregate_weighted(contributions, weights)

    # Compute agreement score
    agreement = compute_agreement(contributions, strategy, weights)

    # Adjust confidence: base confidence × agreement penalty
    raw_confidence = sum(c.confidence for c in contributions) / len(contributions)
    adjusted_confidence = raw_confidence * agreement

    # Detect outliers
    outliers = detect_outliers(contributions, strategy, weights)

    return ConsensusSignal(
        ticker="",  # Will be set by caller
        signal=_numeric_to_signal(score),
        score=round(score, 4),
        confidence=round(adjusted_confidence, 2),
        agreement=round(agreement, 4),
        contributions=contributions,
        outliers=outliers,
        strategy=strategy,
    )


def _aggregate_weighted(
    contributions: list[AgentContribution],
    weights: dict[str, float],
) -> float:
    """Weighted average: score = Σ(w_i × signal_i × confidence_i) / Σ(w_i × confidence_i)."""
    total_weight = 0.0
    weighted_sum = 0.0

    for c in contributions:
        w = weights.get(c.agent_name, 1.0)
        signal_val = _signal_to_numeric(c.signal)
        effective_weight = w * (c.confidence / 100.0)
        weighted_sum += signal_val * effective_weight
        total_weight += effective_weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight


def _aggregate_majority(
    contributions: list[AgentContribution],
    weights: dict[str, float],
) -> float:
    """Majority vote: pick the signal category with the most weighted votes."""
    counter: Counter = Counter()

    for c in contributions:
        w = weights.get(c.agent_name, 1.0)
        counter[c.signal.lower()] += w

    winner = counter.most_common(1)[0][0]
    total = sum(counter.values())
    winner_share = counter[winner] / total if total > 0 else 0.0

    # Scale the score by the winner's share to reflect conviction
    numeric = _signal_to_numeric(winner)
    return numeric * winner_share


def _aggregate_mean(contributions: list[AgentContribution]) -> float:
    """Simple arithmetic mean of numeric signal values."""
    if not contributions:
        return 0.0
    return sum(_signal_to_numeric(c.signal) for c in contributions) / len(contributions)


def compute_agreement(
    contributions: list[AgentContribution],
    strategy: str = "weighted",
    weights: Optional[dict[str, float]] = None,
) -> float:
    """Compute how much the agents agree (0 = total disagreement, 1 = unanimous).

    For 'majority' strategy: share of votes for the winning camp.
    For other strategies: 1 - (stddev / max possible stddev).
    """
    if len(contributions) <= 1:
        return 1.0

    if weights is None:
        weights = {}

    if strategy == "majority":
        counter: Counter = Counter()
        for c in contributions:
            w = weights.get(c.agent_name, 1.0)
            counter[c.signal.lower()] += w
        total = sum(counter.values())
        winner_count = counter.most_common(1)[0][1]
        return winner_count / total if total > 0 else 0.0

    # For weighted and mean: use stddev-based agreement
    numeric_signals = [_signal_to_numeric(c.signal) for c in contributions]
    mean_val = sum(numeric_signals) / len(numeric_signals)
    variance = sum((s - mean_val) ** 2 for s in numeric_signals) / len(numeric_signals)
    stddev = variance ** 0.5

    # Max possible stddev when half are +1 and half are -1
    max_stddev = 1.0
    agreement = 1.0 - (stddev / max_stddev)
    return max(0.0, min(1.0, agreement))


def detect_outliers(
    contributions: list[AgentContribution],
    strategy: str = "weighted",
    weights: Optional[dict[str, float]] = None,
) -> list[str]:
    """Detect agents whose signals deviate significantly from the group consensus.

    Uses standard deviation from mean signal as the outlier criterion.
    Returns agent names of detected outliers.
    """
    if len(contributions) < 3:
        # Need at least 3 agents to meaningfully detect outliers
        return []

    if weights is None:
        weights = {}

    numeric_signals = [_signal_to_numeric(c.signal) for c in contributions]
    mean_val = sum(numeric_signals) / len(numeric_signals)
    variance = sum((s - mean_val) ** 2 for s in numeric_signals) / len(numeric_signals)
    stddev = variance ** 0.5

    if stddev == 0:
        return []  # Perfect agreement, no outliers

    outliers = []
    for c in contributions:
        deviation = abs(_signal_to_numeric(c.signal) - mean_val)
        if deviation > OUTLIER_STDDEV_MULTIPLIER * stddev:
            outliers.append(c.agent_name)

    return outliers


def build_consensus_result(
    signals_by_ticker: dict[str, list[AgentContribution]],
    strategy: str = "weighted",
    weights: Optional[dict[str, float]] = None,
) -> ConsensusResult:
    """Build a full ConsensusResult from per-ticker agent contributions.

    Args:
        signals_by_ticker: Dictionary of ticker → list of agent contributions
        strategy: Aggregation strategy
        weights: Optional per-agent weights

    Returns:
        ConsensusResult with consensus signals for all tickers.
    """
    consensus_signals: dict[str, ConsensusSignal] = {}

    for ticker, contributions in signals_by_ticker.items():
        if not contributions:
            # No signals at all — create a neutral consensus
            consensus_signals[ticker] = ConsensusSignal(
                ticker=ticker,
                signal="neutral",
                score=0.0,
                confidence=0.0,
                agreement=0.0,
                strategy=strategy,
            )
            continue

        signal = aggregate_signals(contributions, strategy, weights)
        signal.ticker = ticker
        consensus_signals[ticker] = signal

    # Build summary
    summary_parts = []
    for ticker, cs in consensus_signals.items():
        outlier_str = ""
        if cs.outliers:
            outlier_str = f" (outliers: {', '.join(cs.outliers)})"
        summary_parts.append(
            f"{ticker}: {cs.signal.upper()} "
            f"(score={cs.score:+.3f}, conf={cs.confidence:.0f}, "
            f"agree={cs.agreement:.0%}){outlier_str}"
        )

    return ConsensusResult(
        signals=consensus_signals,
        summary=" | ".join(summary_parts) if summary_parts else "No signals",
    )
