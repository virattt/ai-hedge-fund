"""Build a Serenity research record from a bottleneck hypothesis + references.

The caller (human or an LLM proposing a bottleneck) supplies the scorecard and a
list of source URLs with claim/excerpt text. This module derives source types +
substantiation + the computed grade deterministically and persists the record
with a non-null disclaimer (PRD v4 §9.6, §9.9).
"""

from sqlalchemy.orm import Session

from src.compliance import research_disclaimer
from src.serenity.evidence import classify_reference
from src.serenity.grading import grade_evidence, recommended_action, serenity_score
from src.storage.models import (
    EvidenceGrade,
    EvidenceReference,
    SerenityResearchRecord,
)


def build_record(
    session: Session,
    *,
    theme: str,
    references: list[dict],
    scorecard: dict,
    ticker: str | None = None,
    platform_key: str | None = None,
    chain_layer: str | None = None,
    bottleneck_hypothesis: str | None = None,
    risks: list[str] | None = None,
    downgrade_triggers: list[str] | None = None,
    min_grade: EvidenceGrade = EvidenceGrade.C,
) -> SerenityResearchRecord:
    """Create + persist a SerenityResearchRecord and its EvidenceReferences.

    ``references`` items: ``{source_url, claim_summary?, excerpt?}``.
    """
    classified = [
        {
            **classify_reference(
                source_url=ref["source_url"],
                claim_summary=ref.get("claim_summary"),
                excerpt=ref.get("excerpt"),
            ),
            "source_url": ref["source_url"],
            "claim_summary": ref.get("claim_summary"),
            "excerpt": ref.get("excerpt"),
        }
        for ref in references
    ]

    grade = grade_evidence(classified)
    score = serenity_score(scorecard, grade, min_grade=min_grade)
    action = recommended_action(score, grade)
    disclaimer, disclaimer_version = research_disclaimer()

    record = SerenityResearchRecord(
        ticker=ticker,
        platform_key=platform_key,
        theme=theme,
        chain_layer=chain_layer,
        bottleneck_hypothesis=bottleneck_hypothesis,
        scorecard=scorecard,
        evidence_grade=grade.value,
        serenity_score=score,
        recommended_action=action.value,
        risks=risks,
        downgrade_triggers=downgrade_triggers,
        disclaimer=disclaimer,
        disclaimer_version=disclaimer_version,
    )
    session.add(record)
    session.flush()  # need record.id for evidence FK

    for c in classified:
        session.add(
            EvidenceReference(
                record_id=record.id,
                source_url=c["source_url"],
                source_host=c["source_host"],
                source_type=c["source_type"].value,
                substantiated=c["substantiated"],
                excerpt=c["excerpt"],
                claim_summary=c["claim_summary"],
            )
        )
    session.flush()
    return record
