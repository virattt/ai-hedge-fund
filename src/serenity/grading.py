"""Deterministic evidence grading + bottleneck scorecard (PRD v4 §9.6, §11.5).

The LLM proposes the bottleneck and summarizes sources; this code computes the
grade from substantiated, allowlisted references with per-host compounding caps
(anti URL-flooding), and converts the bottleneck scorecard into a 0-100 score
gated by the grade. Zero substantiated sources ⇒ grade F ⇒ score withheld
(None → pool bootstrap, no reward for absent evidence).
"""

from collections import defaultdict

from src.storage.models import EvidenceGrade, RecommendedAction, SourceType

# Bottleneck dimensions (Serenity method §5.2): the harder/rarer the link, the higher.
SCORECARD_DIMENSIONS: tuple[str, ...] = (
    "supplier_concentration",  # few suppliers / high concentration
    "validation_cycle",  # long qualification/validation cycles
    "capacity_expansion",  # hard to expand capacity
    "certification_strictness",  # strict certification barriers
    "purity_precision",  # high purity/precision requirements
)
_DIM_MAX = 4  # each dimension scored 0..4

_SOURCE_TYPE_WEIGHT: dict[SourceType, int] = {
    SourceType.FILING: 3,
    SourceType.REGULATORY: 3,
    SourceType.PATENT: 2,
    SourceType.EARNINGS: 2,
    SourceType.NEWS: 1,
    SourceType.UNVERIFIED: 0,
}
_PER_HOST_CAP = 2  # at most 2 references per host count toward the grade
_GRADE_THRESHOLDS = ((6, EvidenceGrade.A), (4, EvidenceGrade.B), (2, EvidenceGrade.C), (1, EvidenceGrade.D))
_GRADE_RANK = {EvidenceGrade.F: 0, EvidenceGrade.D: 1, EvidenceGrade.C: 2, EvidenceGrade.B: 3, EvidenceGrade.A: 4}


def grade_rank(grade: EvidenceGrade | str) -> int:
    return _GRADE_RANK[EvidenceGrade(grade)]


def grade_evidence(refs: list[dict]) -> EvidenceGrade:
    """Compute an evidence grade from classified references.

    ``refs`` are dicts with ``source_host``, ``source_type``, ``substantiated``.
    Only substantiated, allowlisted refs count; per-host cap prevents flooding.
    """
    # Strongest sources first so the per-host cap keeps the best.
    ordered = sorted(refs, key=lambda r: _SOURCE_TYPE_WEIGHT.get(SourceType(r["source_type"]), 0), reverse=True)
    per_host: dict[str, int] = defaultdict(int)
    total = 0
    for r in ordered:
        if not r.get("substantiated"):
            continue
        weight = _SOURCE_TYPE_WEIGHT.get(SourceType(r["source_type"]), 0)
        if weight == 0:
            continue
        host = r.get("source_host") or "?"
        if per_host[host] >= _PER_HOST_CAP:
            continue
        per_host[host] += 1
        total += weight

    for threshold, grade in _GRADE_THRESHOLDS:
        if total >= threshold:
            return grade
    return EvidenceGrade.F


def normalize_scorecard(scorecard: dict) -> float:
    """Sum the five 0-4 dimensions → 0-100. Missing dimensions count as 0."""
    raw = sum(min(_DIM_MAX, max(0, int(scorecard.get(dim, 0)))) for dim in SCORECARD_DIMENSIONS)
    return raw / (_DIM_MAX * len(SCORECARD_DIMENSIONS)) * 100.0


def serenity_score(scorecard: dict, grade: EvidenceGrade, *, min_grade: EvidenceGrade = EvidenceGrade.C) -> float | None:
    """0-100 bottleneck score, or None if evidence grade is below ``min_grade``.

    None means the Serenity axis is *withheld* for this entry (→ pool bootstrap),
    never scored 0 — absence of evidence must not look like weak evidence.
    """
    if grade_rank(grade) < grade_rank(min_grade):
        return None
    return normalize_scorecard(scorecard)


def recommended_action(score: float | None, grade: EvidenceGrade) -> RecommendedAction:
    if grade == EvidenceGrade.F or score is None:
        return RecommendedAction.DEMOTE
    if grade_rank(grade) >= grade_rank(EvidenceGrade.B) and score >= 60.0:
        return RecommendedAction.PROMOTE
    return RecommendedAction.HOLD
