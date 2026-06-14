"""Deterministic-first platform classification (PRD v4 §9.5).

Given a candidate's text metadata (name/sector/industry) plus any curated
``platforms`` labels from the seed CSV, assign platform labels with a confidence
in [0, 1]. This phase is deterministic only; an optional cheap-tier LLM rationale
is an expansion-phase addition. Curated seed labels are the strongest
deterministic signal; keyword matching over text is the fallback/augment.

The classifier output feeds ``platform_fit_score`` (= confidence * 100) in the
scoring composite (PRD §11.2).
"""

from dataclasses import dataclass

from src.observing_pools.platforms import PLATFORM_BY_KEY, PLATFORM_KEYS, PlatformDef

# Confidence assigned to a curated seed label (high, but not certain — keeps room
# for human review before auto-promotion to ``active``, PRD §9.5).
SEED_LABEL_CONFIDENCE = 0.9
# Keyword-match confidence: base + per-hit increment, capped below seed labels.
_KW_BASE = 0.30
_KW_PER_HIT = 0.15
_KW_CAP = 0.85


@dataclass(frozen=True)
class ClassificationResult:
    platform_key: str
    confidence: float
    rationale: str


def _keyword_confidence(text: str, platform: PlatformDef) -> tuple[float, list[str]]:
    """Count distinct keyword hits in ``text`` for one platform → (confidence, hits)."""
    hits = [kw for kw in platform.keywords if kw in text]
    if not hits:
        return 0.0, []
    conf = min(_KW_CAP, _KW_BASE + _KW_PER_HIT * len(hits))
    return conf, hits


def classify_candidate(
    *,
    name: str | None,
    sector: str | None,
    industry: str | None,
    explicit_platforms: list[str] | None = None,
) -> dict[str, ClassificationResult]:
    """Classify one candidate. Returns {platform_key: ClassificationResult}.

    Merges curated seed labels (high confidence) with keyword inference over the
    name/sector/industry text (lower confidence), taking the max per platform.
    """
    text = " ".join(part for part in (name, sector, industry) if part).lower()
    explicit = {p.strip() for p in (explicit_platforms or []) if p.strip()}

    results: dict[str, ClassificationResult] = {}

    for key in PLATFORM_KEYS:
        platform = PLATFORM_BY_KEY[key]
        candidates: list[ClassificationResult] = []

        if key in explicit:
            candidates.append(ClassificationResult(key, SEED_LABEL_CONFIDENCE, "curated seed label"))

        kw_conf, hits = _keyword_confidence(text, platform)
        if kw_conf > 0:
            candidates.append(ClassificationResult(key, kw_conf, f"keyword match: {', '.join(hits)}"))

        if candidates:
            # Highest-confidence rule wins for this platform.
            results[key] = max(candidates, key=lambda r: r.confidence)

    # Any explicit label not in the taxonomy is an ingestion error — surface loudly.
    unknown = explicit - set(PLATFORM_KEYS)
    if unknown:
        raise ValueError(f"unknown platform label(s) in seed data: {sorted(unknown)}")

    return results
