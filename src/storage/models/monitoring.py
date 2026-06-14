"""Monitoring + opportunity-report models (PRD v4 §10).

User-facing labels are descriptive (``ReportLabel``), never directional buy/sell.
The disclaimer columns are NOT NULL — combined with the ``serialize_report``
chokepoint, a report cannot be emitted or stored without one (PRD M7/§12).
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


class ReportLabel(StrEnum):
    """Descriptive (non-directional) label surfaced to users (PRD §9.9)."""

    THESIS_SUPPORTIVE = "thesis-supportive"
    THESIS_CHALLENGING = "thesis-challenging"
    MIXED = "mixed"
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"


class Granularity(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class MonitorConfig(Base):
    """A reusable watchlist + analysis-flow configuration (PRD §9.7)."""

    __tablename__ = "monitor_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    tickers = Column(JSON, nullable=False, default=list)
    platform_keys = Column(JSON, nullable=True)
    granularity = Column(String(16), nullable=False, default=Granularity.WEEKLY.value)
    schedule = Column(String(50), nullable=True)  # cron/enum (scheduler is an expansion phase)
    selected_analysts = Column(JSON, nullable=True)
    lookback_window = Column(String(32), nullable=True)
    trigger_config = Column(JSON, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OpportunityReport(Base):
    """A research-only opportunity report. Emitted only via ``serialize_report``."""

    __tablename__ = "opportunity_reports"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitor_configs.id"), nullable=True, index=True)
    ticker = Column(String(32), nullable=False, index=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    label = Column(String(32), nullable=False, default=ReportLabel.INSUFFICIENT_EVIDENCE.value)
    confidence = Column(Float, nullable=True)
    degraded = Column(Boolean, nullable=False, default=False)
    time_horizon = Column(String(32), nullable=True)
    summary = Column(Text, nullable=True)
    agent_signals = Column(JSON, nullable=True)
    serenity_context = Column(JSON, nullable=True)
    risks = Column(JSON, nullable=True)
    next_checks = Column(JSON, nullable=True)

    # Enforced NOT NULL; the serializer also refuses to emit without these.
    disclaimer = Column(Text, nullable=False)
    disclaimer_version = Column(String(32), nullable=False)
