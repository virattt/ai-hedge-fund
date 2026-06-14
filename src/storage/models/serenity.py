"""Serenity supply-chain-bottleneck research models (PRD v4 §10).

Evidence grade is *computed* from substantiated, allowlist-sourced references —
the LLM may summarize but never assigns a grade or sets ``source_type`` (PRD
§9.6, §11.5). ``source_type`` is host-derived, never accepted from input.
"""

from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from src.storage.database import Base


class EvidenceGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class SourceType(StrEnum):
    FILING = "filing"  # SEC/EDGAR
    PATENT = "patent"  # USPTO / Google Patents
    REGULATORY = "regulatory"
    EARNINGS = "earnings"
    NEWS = "news"
    UNVERIFIED = "unverified"  # host not on allowlist → never counts toward grade


class RecommendedAction(StrEnum):
    PROMOTE = "promote"
    HOLD = "hold"
    DEMOTE = "demote"


class SerenityResearchRecord(Base):
    """One bottleneck research record per theme/candidate."""

    __tablename__ = "serenity_research_records"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(32), nullable=True, index=True)
    platform_key = Column(String(50), nullable=True, index=True)
    theme = Column(String(255), nullable=False)
    chain_layer = Column(String(120), nullable=True)
    bottleneck_hypothesis = Column(Text, nullable=True)

    scorecard = Column(JSON, nullable=True)  # {dimension: 0-4}
    evidence_grade = Column(String(2), nullable=True)  # computed
    serenity_score = Column(Float, nullable=True)  # 0-100 or None (below min grade → bootstrap)
    recommended_action = Column(String(16), nullable=True)  # promote/hold/demote
    risks = Column(JSON, nullable=True)
    downgrade_triggers = Column(JSON, nullable=True)

    # Disclaimer carried as data; enforced as an invariant at serialization (PRD M7/§12).
    disclaimer = Column(Text, nullable=False)
    disclaimer_version = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EvidenceReference(Base):
    """A retrieved/asserted source backing a research record. ``substantiated`` and
    ``source_type`` are set by deterministic code, never by the LLM/user."""

    __tablename__ = "evidence_references"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("serenity_research_records.id"), nullable=False, index=True)
    source_url = Column(String(1024), nullable=False)
    source_host = Column(String(255), nullable=True)
    source_type = Column(String(32), nullable=False, default=SourceType.UNVERIFIED.value)  # host-derived
    substantiated = Column(Boolean, nullable=False, default=False)  # deterministic claim↔text check
    excerpt = Column(Text, nullable=True)
    claim_summary = Column(Text, nullable=True)  # LLM-provided, untrusted for grading
    created_at = Column(DateTime(timezone=True), server_default=func.now())
