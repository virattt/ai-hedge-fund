"""Pure aggregation math for the consensus layer — no LLM, no state.

``aggregate_signals`` takes a dict of ``{agent_name: {"signal", "confidence"}}``
for a single ticker and returns a ``ConsensusSignal`` with a composite score,
aggregate confidence, and an agreement measure.
"""

from __future__ import annotations

import logging

from typing_extensions import Literal

from src.consensus.models import AgentContribution, ConsensusSignal

logger = logging.getLogger(__name__)

_SIGNAL_TO_SIGN: dict[str, int] = {"bullish": 1, "bearish": -1, "neutral": 0}
_VALID_SIGNALS = frozenset(_SIGNAL_TO_SIGN.keys())

Strategy = Literal["weighted", "majority", "mean"]


def compute_agreement(weight_by_camp: dict[str, float]) -> float:
    """Return the share of total weight held by the largest camp, in [0, 1].

    Unanimous → 1.0; perfect 2-way split → 0.5; perfect 3-way split → ~0.333.
    Returns 0.0 when no weight is present.
    """
    total = sum(weight_by_camp.values())
    if total <= 0.0:
        return 0.0
    return max(weight_by_camp.values()) / total


def aggregate_signals(
    ticker_signals: dict[str, dict],
    *,
    weights: dict[str, float] | None = None,
    strategy: Strategy = "weighted",
    neutral_deadband: float = 0.15,
) -> ConsensusSignal:
    """Combine per-agent signals for one ticker into a single ``ConsensusSignal``.

    Args:
        ticker_signals: ``{agent_name: {"signal": "bullish"|"bearish"|"neutral",
            "confidence": 0-100}}``. Entries with missing or invalid signals are
            silently skipped.
        weights: optional ``{agent_name: weight}`` overrides. Missing agents
            default to ``1.0``. Negative weights are clamped to ``0.0``.
        strategy: ``"weighted"`` (default) scales by ``weight * confidence``;
            ``"majority"`` ignores confidence; ``"mean"`` ignores custom weights.
        neutral_deadband: ``|score|`` below this threshold maps to ``"neutral"``.
    """

    entries = _normalise_inputs(ticker_signals, weights, strategy)
    if not entries:
        return _empty_consensus()

    contributions: dict[str, AgentContribution] = {}
    vote_counts = {"bullish": 0, "bearish": 0, "neutral": 0}
    weight_by_camp = {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}
    score_numerator = 0.0
    weight_sum = 0.0
    conf_weighted_sum = 0.0

    for agent, signal, confidence, weight in entries:
        sign = _SIGNAL_TO_SIGN[signal]
        conf_frac = 1.0 if strategy == "majority" else confidence / 100.0
        contribution = sign * weight * conf_frac

        contributions[agent] = AgentContribution(
            signal=signal,
            confidence=confidence,
            weight=weight,
            contribution=contribution,
        )
        vote_counts[signal] += 1
        weight_by_camp[signal] += weight
        score_numerator += contribution
        weight_sum += weight
        conf_weighted_sum += weight * confidence

    if weight_sum <= 0.0:
        score = 0.0
        weighted_mean_conf = 0.0
    else:
        score = score_numerator / weight_sum
        weighted_mean_conf = conf_weighted_sum / weight_sum

    # Clamp against floating point drift
    score = max(-1.0, min(1.0, score))

    agreement = compute_agreement(weight_by_camp)
    aggregate_confidence = agreement * weighted_mean_conf

    discrete = _apply_deadband(score, neutral_deadband)
    reasoning = _build_reasoning(discrete, score, agreement, vote_counts, contributions)

    return ConsensusSignal(
        signal=discrete,
        score=score,
        confidence=aggregate_confidence,
        agreement=agreement,
        vote_breakdown=vote_counts,
        contributions=contributions,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _normalise_inputs(
    ticker_signals: dict[str, dict],
    weights: dict[str, float] | None,
    strategy: Strategy,
) -> list[tuple[str, str, float, float]]:
    """Filter and coerce raw signal dicts into ``(agent, signal, conf, weight)``."""
    weights = weights or {}
    out: list[tuple[str, str, float, float]] = []

    for agent, payload in ticker_signals.items():
        if not isinstance(payload, dict):
            continue
        signal = payload.get("signal")
        if signal not in _VALID_SIGNALS:
            logger.debug("consensus: skipping %s — invalid signal %r", agent, signal)
            continue

        confidence = _coerce_confidence(payload.get("confidence"))

        if strategy == "mean":
            weight = 1.0
        else:
            raw_weight = weights.get(agent, 1.0)
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError):
                weight = 1.0
            if weight < 0.0:
                weight = 0.0

        out.append((agent, signal, confidence, weight))

    return out


def _coerce_confidence(value) -> float:
    """Clamp confidence into [0, 100]. Bad values become 0.0."""
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    if conf != conf:  # NaN check without importing math
        return 0.0
    if conf < 0.0:
        return 0.0
    if conf > 100.0:
        return 100.0
    return conf


def _apply_deadband(score: float, deadband: float) -> str:
    if abs(score) < deadband:
        return "neutral"
    return "bullish" if score > 0.0 else "bearish"


def _empty_consensus() -> ConsensusSignal:
    return ConsensusSignal(
        signal="neutral",
        score=0.0,
        confidence=0.0,
        agreement=0.0,
        vote_breakdown={"bullish": 0, "bearish": 0, "neutral": 0},
        contributions={},
        reasoning="No valid analyst signals",
    )


def _build_reasoning(
    discrete: str,
    score: float,
    agreement: float,
    vote_counts: dict[str, int],
    contributions: dict[str, AgentContribution],
) -> str:
    top = sorted(
        contributions.items(),
        key=lambda item: abs(item[1].contribution),
        reverse=True,
    )[:3]
    top_str = ", ".join(f"{agent} ({c.contribution:+.2f})" for agent, c in top)
    return (
        f"{discrete} (score={score:+.2f}, agreement={agreement:.2f}); "
        f"bull/bear/neut = "
        f"{vote_counts['bullish']}/{vote_counts['bearish']}/{vote_counts['neutral']}; "
        f"top: {top_str}"
    )
