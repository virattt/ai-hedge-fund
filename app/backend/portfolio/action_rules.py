"""Educational action label rules.

Maps agent pipeline output to one of:
- ADD CAUTIOUSLY
- HOLD
- WATCH
- REVIEW
- REDUCE / REVIEW EXIT

Never outputs BUY NOW or SELL NOW.
"""

from typing import Optional

ALLOWED_LABELS = ["ADD CAUTIOUSLY", "HOLD", "WATCH", "REVIEW", "REDUCE / REVIEW EXIT"]

# Numeric mapping for signal aggregation
SIGNAL_SCORE = {
    "bullish": 1.0,
    "neutral": 0.0,
    "bearish": -1.0,
}

# Minimum magnitude to count a signal as directional in consensus voting
_DIRECTIONAL_THRESHOLD = 0.3


def determine_educational_action(
    technical_signal: Optional[str],
    technical_confidence: Optional[float],
    fundamental_signal: Optional[str],
    fundamental_confidence: Optional[float],
    sentiment_signal: Optional[str],
    valuation_signal: Optional[str],
    risk_remaining_limit: Optional[float],
    portfolio_manager_action: Optional[str],
    rsi_14: Optional[float] = None,
) -> tuple[str, float, list[str], list[str], list[str]]:
    """Determine educational action label from agent outputs.

    Returns:
        (action_label, confidence, positive_factors, risk_factors, uncertainties)
    """
    positive_factors: list[str] = []
    risk_factors: list[str] = []
    uncertainties: list[str] = []

    # --- Gather signals with weights ---
    # Technical and fundamental get higher weight; sentiment/valuation are supporting
    weighted_signals: list[tuple[float, float]] = []  # (score, weight)

    if technical_signal in SIGNAL_SCORE:
        tech_weight = 1.5
        weighted_signals.append((SIGNAL_SCORE[technical_signal], tech_weight))
    if fundamental_signal in SIGNAL_SCORE:
        fund_weight = 1.5
        weighted_signals.append((SIGNAL_SCORE[fundamental_signal], fund_weight))
    if sentiment_signal in SIGNAL_SCORE:
        sent_weight = 1.0
        weighted_signals.append((SIGNAL_SCORE[sentiment_signal], sent_weight))
    if valuation_signal in SIGNAL_SCORE:
        val_weight = 1.2
        weighted_signals.append((SIGNAL_SCORE[valuation_signal], val_weight))

    # Count signals
    signals = [technical_signal, fundamental_signal, sentiment_signal, valuation_signal]
    available_signals = [s for s in signals if s in SIGNAL_SCORE]
    total_agents = 4
    data_completeness = len(available_signals) / total_agents

    bullish_count = sum(1 for s in available_signals if s == "bullish")
    bearish_count = sum(1 for s in available_signals if s == "bearish")
    neutral_count = sum(1 for s in available_signals if s == "neutral")
    none_count = total_agents - len(available_signals)

    # Compute weighted consensus score: -1.0 (full bearish) to +1.0 (full bullish)
    if weighted_signals:
        total_weight = sum(w for _, w in weighted_signals)
        consensus_score = sum(s * w for s, w in weighted_signals) / total_weight
    else:
        consensus_score = 0.0

    # Measure agreement: how aligned are the signals?
    if len(available_signals) >= 2:
        agreement = 1.0 - (min(bullish_count, bearish_count) / len(available_signals))
    else:
        agreement = 0.5

    # --- Build factor lists ---
    if technical_signal == "bullish":
        positive_factors.append("Technical trend is positive")
    elif technical_signal == "bearish":
        risk_factors.append("Technical trend is negative")

    if fundamental_signal == "bullish":
        positive_factors.append("Fundamentals are strong")
    elif fundamental_signal == "bearish":
        risk_factors.append("Fundamental weakness detected")

    if sentiment_signal == "bullish":
        positive_factors.append("Market sentiment is positive")
    elif sentiment_signal == "bearish":
        risk_factors.append("Negative market sentiment")

    if valuation_signal == "bullish":
        positive_factors.append("Valuation appears reasonable/undervalued")
    elif valuation_signal == "bearish":
        risk_factors.append("Valuation appears expensive")

    if none_count > 0:
        uncertainties.append(f"{none_count} of 4 agents returned no data")

    # RSI-based context
    rsi_high = rsi_14 is not None and rsi_14 > 70
    rsi_low = rsi_14 is not None and rsi_14 < 30

    if rsi_high:
        risk_factors.append(f"RSI is elevated ({rsi_14:.0f}) — overbought territory")
    if rsi_low:
        positive_factors.append(f"RSI suggests oversold ({rsi_14:.0f}) — potential rebound")

    # Detect high-risk from risk manager
    high_risk = False
    if risk_remaining_limit is not None and risk_remaining_limit < 0:
        high_risk = True
        risk_factors.append("Position exceeds recommended risk limit")

    # Detect conflicting signals
    has_conflict = bullish_count > 0 and bearish_count > 0
    if has_conflict:
        uncertainties.append("Conflicting signals — agents disagree on direction")

    # --- Confidence calibration ---
    # Base confidence from agreement strength and data completeness
    # Range: 30-80%. Never 0%, never 100%.
    signal_strength = abs(consensus_score)  # 0.0 to 1.0
    base_confidence = 30.0 + (signal_strength * 30.0) + (agreement * 15.0) + (data_completeness * 5.0)

    # Bonus for high data quality (4 agents all reporting)
    if len(available_signals) >= 4:
        base_confidence += 5.0

    # Incorporate agent-reported confidence (if available and meaningful)
    agent_confidences = []
    if technical_confidence is not None and technical_confidence > 10.0:
        agent_confidences.append(technical_confidence)
    if fundamental_confidence is not None and fundamental_confidence > 10.0:
        agent_confidences.append(fundamental_confidence)

    if agent_confidences:
        avg_agent_conf = sum(agent_confidences) / len(agent_confidences)
        # Blend: 70% our rule-based calc, 30% agent-reported
        base_confidence = base_confidence * 0.7 + avg_agent_conf * 0.3

    # Penalize confidence when signals conflict
    if has_conflict:
        conflict_penalty = min(bullish_count, bearish_count) * 8.0
        base_confidence -= conflict_penalty

    # Penalize for sparse data
    if none_count >= 2:
        base_confidence -= 8.0

    confidence = max(30.0, min(80.0, base_confidence))

    # --- Decision rules ---

    # Rule: Insufficient data → WATCH
    if none_count >= 3:
        uncertainties.append("Insufficient data for confident assessment")
        return "WATCH", 30.0, positive_factors, risk_factors, uncertainties

    # Rule: RSI extreme + valuation confirms → stronger directional signal
    if rsi_high and valuation_signal == "bearish":
        if bearish_count >= 2:
            return "REDUCE / REVIEW EXIT", confidence, positive_factors, risk_factors, uncertainties
        else:
            return "REVIEW", confidence, positive_factors, risk_factors, uncertainties

    # Rule: Strong bullish consensus (score > 0.5, good agreement, no high risk)
    if consensus_score > 0.5 and agreement >= 0.7 and not high_risk:
        if fundamental_signal == "bullish" and valuation_signal in ("bullish", "neutral"):
            return "ADD CAUTIOUSLY", confidence, positive_factors, risk_factors, uncertainties
        return "HOLD", confidence, positive_factors, risk_factors, uncertainties

    # Rule: Strong bearish consensus (score < -0.5, good agreement)
    if consensus_score < -0.5 and agreement >= 0.7:
        if bearish_count >= 3:
            return "REDUCE / REVIEW EXIT", confidence, positive_factors, risk_factors, uncertainties
        return "REVIEW", confidence, positive_factors, risk_factors, uncertainties

    # Rule: Moderate bullish lean (no conflict)
    if consensus_score > 0.2 and not has_conflict and not high_risk:
        return "HOLD", confidence, positive_factors, risk_factors, uncertainties

    # Rule: Moderate bearish lean
    if consensus_score < -0.2 and not has_conflict:
        if high_risk:
            return "REDUCE / REVIEW EXIT", confidence, positive_factors, risk_factors, uncertainties
        return "REVIEW", confidence, positive_factors, risk_factors, uncertainties

    # Rule: Mixed signals with conflict
    if has_conflict:
        if high_risk:
            return "REVIEW", confidence, positive_factors, risk_factors, uncertainties
        return "HOLD", confidence, positive_factors, risk_factors, uncertainties

    # Default: mostly neutral or weak signals → WATCH
    if not positive_factors and not risk_factors:
        uncertainties.append("No strong directional signals detected")
    return "WATCH", confidence, positive_factors, risk_factors, uncertainties
