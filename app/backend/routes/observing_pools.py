"""Read-only API for observing pools, reports, and platforms (PRD v4 §14).

Loopback-bound (research-only). Every report is projected through
``serialize_report`` so the disclaimer invariant holds on the API surface too.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.database.connection import get_db
from src.monitoring.serialize import serialize_report
from src.observing_pools.platforms import PLATFORM_KEYS
from src.storage.models import (
    InnovationPlatform,
    ObservationPoolEntry,
    OpportunityReport,
    SerenityResearchRecord,
)

router = APIRouter()


def _entry_to_dict(e: ObservationPoolEntry) -> dict:
    return {
        "ticker": e.ticker,
        "platform_key": e.platform_key,
        "status": e.status,
        "rank": e.rank,
        "composite_score": e.composite_score,
        "composite_formula_version": e.composite_formula_version,
        "components": {
            "platform_fit": e.platform_fit_score,
            "value_investor": e.value_investor_score,
            "innovation_growth": e.innovation_growth_score,
            "risk_adjusted_momentum": e.risk_adjusted_momentum_score,
            "serenity_bottleneck": e.serenity_bottleneck_score,
        },
        "score_breakdown": e.score_breakdown,
        "rationale": e.rationale,
    }


@router.get("/innovation-platforms")
def list_platforms(db: Session = Depends(get_db)) -> list[dict]:
    platforms = db.query(InnovationPlatform).order_by(InnovationPlatform.key).all()
    return [{"key": p.key, "name": p.name, "description": p.description, "enabled": p.enabled} for p in platforms]


@router.get("/observing-pools/{platform_key}")
def get_pool(platform_key: str, db: Session = Depends(get_db)) -> dict:
    if platform_key not in PLATFORM_KEYS:
        raise HTTPException(status_code=404, detail=f"unknown platform '{platform_key}'")
    ranked = (
        db.query(ObservationPoolEntry)
        .filter_by(platform_key=platform_key)
        .filter(ObservationPoolEntry.rank.isnot(None))
        .order_by(ObservationPoolEntry.rank)
        .all()
    )
    return {"platform_key": platform_key, "count": len(ranked), "entries": [_entry_to_dict(e) for e in ranked]}


@router.get("/serenity/research/{ticker}")
def get_serenity(ticker: str, db: Session = Depends(get_db)) -> list[dict]:
    records = db.query(SerenityResearchRecord).filter_by(ticker=ticker.upper()).order_by(SerenityResearchRecord.id.desc()).all()
    return [
        {
            "id": r.id, "ticker": r.ticker, "platform_key": r.platform_key, "theme": r.theme,
            "chain_layer": r.chain_layer, "bottleneck_hypothesis": r.bottleneck_hypothesis,
            "evidence_grade": r.evidence_grade, "serenity_score": r.serenity_score,
            "recommended_action": r.recommended_action,
            "disclaimer": r.disclaimer, "disclaimer_version": r.disclaimer_version,
        }
        for r in records
    ]


@router.get("/opportunity-reports")
def list_reports(db: Session = Depends(get_db), limit: int = 50) -> list[dict]:
    reports = db.query(OpportunityReport).order_by(OpportunityReport.id.desc()).limit(limit).all()
    return [serialize_report(r) for r in reports]  # disclaimer invariant enforced here
