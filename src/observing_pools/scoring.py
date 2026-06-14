"""Pure scoring contract for observing pools (PRD v4 §11.1-11.3).

No I/O, no ORM — just the deterministic math, so it is exhaustively unit-testable
and reproducible. Two separate enums close the v2-review KeyError seam:
``AgentSignal`` (the only input to ``signal_to_score``) vs the user-facing
``ReportLabel`` (defined with the report serializer, not here).

Blended composite (the key design decision in the plan): a *value* axis and a
separate *innovation/growth* axis both contribute, so value discipline cannot
veto innovation exposure — the whole reason the pools exist.
"""

from collections.abc import Iterable, Mapping
from enum import StrEnum

# ── Composite definition ────────────────────────────────────────────────────

COMPONENT_WEIGHTS: dict[str, float] = {
    "platform_fit": 0.25,  # classifier confidence (§9.5)
    "value_investor": 0.30,  # Buffett/Munger/Graham/Pabrai/Fisher/Lynch/Damodaran/Valuation/Fundamentals
    "innovation_growth": 0.20,  # Cathie Wood + Growth Analyst
    "risk_adjusted_momentum": 0.10,  # Technical/Sentiment/News/Burry/Druckenmiller − risk haircut
    "serenity_bottleneck": 0.15,  # Serenity record, gated by evidence grade (§9.6)
}

# Components without which an entry cannot be ranked (excluded, not scored 0).
REQUIRED: frozenset[str] = frozenset({"platform_fit", "value_investor"})

# Versioned composite (PRD F3): Phase 5 ships 4-component (serenity excluded);
# Serenity introduces the 5-component formula. The version is stored on every entry.
FORMULA_4COMP = "v3-4comp"
FORMULA_5COMP = "v3-5comp"

# The four components present in the pre-Serenity (v3-4comp) composite.
_FOURCOMP_KEYS = ("platform_fit", "value_investor", "innovation_growth", "risk_adjusted_momentum")


class AgentSignal(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


def signal_to_score(signal: "AgentSignal | str", confidence: float) -> float:
    """0-100 attractiveness. neutral→50; full-confidence bullish→100; bearish→0.

    Confidence is clamped to [0, 100] to tolerate int|float and the technicals
    0-1 range (scaled to 0-100 at the dict layer; the clamp is the safety net).
    A signal outside the three valid values raises — callers must map unknown/
    degraded outputs to ``neutral`` *before* calling (PRD §8.3 safe-default).
    """
    sig = AgentSignal(signal)  # raises ValueError on anything but bullish/bearish/neutral
    c = max(0.0, min(100.0, float(confidence)))
    directional = {AgentSignal.BULLISH: +c, AgentSignal.BEARISH: -c, AgentSignal.NEUTRAL: 0.0}[sig]
    return (directional + 100.0) / 2.0


def mean_or_none(scores: Iterable[float | None]) -> float | None:
    """Mean over non-None scores; None if none present (component absent)."""
    vals = [s for s in scores if s is not None]
    return sum(vals) / len(vals) if vals else None


def validate_weights(weights: Mapping[str, float]) -> None:
    """Reject rank-inverting / degenerate weight configs (PRD M6)."""
    for key, w in weights.items():
        if not (0.0 <= w <= 1.0):
            raise ValueError(f"weight {key}={w} is outside [0, 1]")
    if sum(weights.values()) <= 0:
        raise ValueError("sum of weights must be > 0")
    for req in REQUIRED:
        if weights.get(req, 0.0) <= 0:
            raise ValueError(f"REQUIRED component '{req}' must have weight > 0")


def build_components(
    values: Mapping[str, float | None],
    *,
    formula_version: str,
    weights: Mapping[str, float] = COMPONENT_WEIGHTS,
) -> dict[str, tuple[float, float | None]]:
    """Assemble the {name: (weight, value)} map for ``composite``.

    For v3-4comp the serenity component is omitted entirely (Phase 5 design);
    for v3-5comp all five are included (serenity value may be None → bootstrap).
    """
    keys = _FOURCOMP_KEYS if formula_version == FORMULA_4COMP else tuple(COMPONENT_WEIGHTS)
    return {k: (weights[k], values.get(k)) for k in keys}


def composite(
    components: Mapping[str, tuple[float, float | None]],
    *,
    pool_serenity_median: float | None,
    formula_version: str,
) -> float | None:
    """Weighted composite over *present* components, normalized by present weight.

    Returns None (→ status ``data_unavailable``, excluded from ranking, NOT scored 0)
    when a REQUIRED component is missing. Implements the F2 bootstrap: in 5-comp
    mode a missing serenity value is either dropped uniformly (zero graded entries
    in the pool → no differential reward) or imputed at the graded-only median.
    """
    comps = dict(components)  # copy — never mutate the caller's mapping

    if formula_version == FORMULA_5COMP and "serenity_bottleneck" in comps:
        weight, value = comps["serenity_bottleneck"]
        if value is None:
            if pool_serenity_median is None:
                # Zero graded entries → drop serenity for everyone this run (identical
                # reweight ⇒ "no evidence" gains no edge over "weak evidence").
                comps.pop("serenity_bottleneck")
            else:
                # Impute neutral (graded-only median), not favorable.
                comps["serenity_bottleneck"] = (weight, pool_serenity_median)

    present = {k: (w, v) for k, (w, v) in comps.items() if v is not None}
    if not REQUIRED.issubset(present):
        return None
    total_weight = sum(w for w, _ in present.values())
    if total_weight <= 0:
        return None
    return sum(w * v for w, v in present.values()) / total_weight
