"""Observing-pool ORM models (Phase 0 subset of PRD v4 §10).

These live on the single shared ``Base`` and are registered via the package
aggregator (``src.storage.models``). Only the four models needed for the
vertical slice are defined here: platform taxonomy, candidate universe, pool
entries (with the full reproducible score breakdown + formula version), and
refresh-run provenance. Serenity, monitor, and report models arrive in later
Phase-0 steps in their own modules.
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
    UniqueConstraint,
)
from sqlalchemy.sql import func

from src.storage.database import Base


class PoolEntryStatus(StrEnum):
    """Lifecycle of a pool entry. Low-confidence stays ``candidate`` and is
    never auto-promoted to ``active`` (PRD §9.5)."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    DATA_UNAVAILABLE = "data_unavailable"  # REQUIRED component missing → excluded from ranking
    DROPPED = "dropped"


class RefreshRunStatus(StrEnum):
    """A run is ``complete`` only with zero fetch errors/ambiguities; otherwise
    ``partial`` (PRD §8.2, §10)."""

    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    ERROR = "error"


class InnovationPlatform(Base):
    """One of the five disruptive-innovation platforms (ARK/Cathie-Wood thesis)."""

    __tablename__ = "innovation_platforms"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False, unique=True, index=True)  # e.g. "ai"
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=False, default=list)  # deterministic classifier seeds
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CandidateSecurity(Base):
    """A security observed in the candidate universe. A ticker may map to many
    platforms; this is the per-ticker identity row (membership lives on
    ``ObservationPoolEntry``)."""

    __tablename__ = "candidate_securities"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=True)
    exchange = Column(String(32), nullable=True)
    region = Column(String(32), nullable=True)
    sector = Column(String(120), nullable=True)
    industry = Column(String(200), nullable=True)
    source = Column(String(120), nullable=False, default="seed")  # seed csv, yfinance, etc.
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ObservationPoolEntry(Base):
    """A ticker's membership + score in one platform pool for the latest refresh.

    Stores all five component scores, the composite, the full ``score_breakdown``
    JSON, and the ``composite_formula_version`` so every composite is reproducible
    (PRD B3). One row per (ticker, platform_key)."""

    __tablename__ = "observation_pool_entries"
    __table_args__ = (UniqueConstraint("ticker", "platform_key", name="uq_pool_ticker_platform"),)

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(32), nullable=False, index=True)
    platform_key = Column(String(50), ForeignKey("innovation_platforms.key"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default=PoolEntryStatus.CANDIDATE.value)

    # Five composite components (PRD §11.2); nullable because any may be absent.
    platform_fit_score = Column(Float, nullable=True)
    value_investor_score = Column(Float, nullable=True)
    innovation_growth_score = Column(Float, nullable=True)
    serenity_bottleneck_score = Column(Float, nullable=True)
    risk_adjusted_momentum_score = Column(Float, nullable=True)

    composite_score = Column(Float, nullable=True)
    composite_formula_version = Column(String(32), nullable=True)  # "v3-4comp" | "v3-5comp"
    score_breakdown = Column(JSON, nullable=True)  # per-agent {signal,confidence,degraded}, weights, bootstrap flags
    rank = Column(Integer, nullable=True, index=True)
    rationale = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)  # list of EvidenceReference ids (Serenity step)

    last_refresh_run_id = Column(Integer, ForeignKey("pool_refresh_runs.id"), nullable=True, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    last_refreshed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PoolRefreshRun(Base):
    """Provenance + cost ledger for one weekly refresh of one-or-more platforms.

    ``status='complete'`` requires zero FetchError/Ambiguous; otherwise
    ``partial`` (PRD §8.2, §10)."""

    __tablename__ = "pool_refresh_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default=RefreshRunStatus.RUNNING.value)

    provider_name = Column(String(64), nullable=True)
    universe_source = Column(String(255), nullable=True)
    universe_version = Column(String(64), nullable=True)
    composite_formula_version = Column(String(32), nullable=True)
    platform_keys = Column(JSON, nullable=True)  # list[str]
    candidate_count = Column(Integer, nullable=True)

    fetch_errors = Column(JSON, nullable=True)  # {ticker: reason}; includes Ambiguous-classified
    rejected = Column(JSON, nullable=True)  # {ticker: reason}
    token_cost = Column(JSON, nullable=True)  # {calls, tokens, est_usd}
    summary = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
