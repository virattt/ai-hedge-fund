"""Fold Serenity scores into an observing pool and recompute as v3-5comp.

Implements the F2 bootstrap exactly: the pool-median is computed over *graded*
entries only; with zero graded entries the Serenity weight is dropped uniformly
(no entry gains an edge from absent evidence); once ≥1 entry is graded, a missing
Serenity value imputes at the graded-only median (neutral). Then the pool is
re-ranked on the new composite.
"""

from statistics import median

from sqlalchemy.orm import Session

from src.observing_pools.scoring import FORMULA_5COMP, build_components, composite
from src.storage.models import ObservationPoolEntry, PoolEntryStatus, SerenityResearchRecord


def _latest_scores_by_ticker(session: Session, platform_key: str) -> dict[str, float | None]:
    """Most-recent Serenity score per ticker for this platform (None = below grade)."""
    records = session.query(SerenityResearchRecord).filter_by(platform_key=platform_key).order_by(SerenityResearchRecord.id).all()
    out: dict[str, float | None] = {}
    for r in records:
        if r.ticker:
            out[r.ticker] = r.serenity_score  # later record wins (ordered by id)
    return out


def apply_serenity_to_pool(session: Session, platform_key: str) -> dict:
    """Set serenity scores on pool entries, recompute v3-5comp, re-rank.

    Returns a summary {graded, median, reranked}.
    """
    score_by_ticker = _latest_scores_by_ticker(session, platform_key)
    graded = [s for s in score_by_ticker.values() if s is not None]
    pool_median = median(graded) if graded else None

    entries = session.query(ObservationPoolEntry).filter_by(platform_key=platform_key).all()
    for e in entries:
        e.serenity_bottleneck_score = score_by_ticker.get(e.ticker)
        values = {
            "platform_fit": e.platform_fit_score,
            "value_investor": e.value_investor_score,
            "innovation_growth": e.innovation_growth_score,
            "risk_adjusted_momentum": e.risk_adjusted_momentum_score,
            "serenity_bottleneck": e.serenity_bottleneck_score,
        }
        comp_map = build_components(values, formula_version=FORMULA_5COMP)
        new_score = composite(comp_map, pool_serenity_median=pool_median, formula_version=FORMULA_5COMP)
        e.composite_score = new_score
        e.composite_formula_version = FORMULA_5COMP
        bd = dict(e.score_breakdown or {})
        bd["serenity"] = {"value": e.serenity_bottleneck_score, "pool_median": pool_median, "graded_count": len(graded)}
        bd["formula_version"] = FORMULA_5COMP
        bd["composite"] = new_score
        e.score_breakdown = bd  # reassign so SQLAlchemy detects the JSON change

    # Re-rank on the new composite; data_unavailable entries keep no rank.
    rankable = sorted((e for e in entries if e.composite_score is not None), key=lambda e: e.composite_score, reverse=True)
    for rank, e in enumerate(rankable, start=1):
        e.rank = rank
        if e.status == PoolEntryStatus.DATA_UNAVAILABLE.value:
            e.status = PoolEntryStatus.CANDIDATE.value
    for e in entries:
        if e.composite_score is None:
            e.rank = None
            e.status = PoolEntryStatus.DATA_UNAVAILABLE.value

    session.flush()
    return {"graded": len(graded), "median": pool_median, "reranked": len(rankable)}
