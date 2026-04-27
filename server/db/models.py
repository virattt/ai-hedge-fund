"""SQLModel ORM tables for run persistence.

Schema mirrors the plan at §B4. Column types are kept to portable SQL
(strings, ints, floats, JSON-as-text) so a Postgres migration is mechanical
(see ADR-002 "Migration to Postgres").
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlmodel import JSON, Column, Field, SQLModel


def _new_id() -> str:
    return uuid4().hex


def _utcnow() -> datetime:
    return datetime.utcnow()


class Run(SQLModel, table=True):
    """A single analyze or backtest invocation."""

    __tablename__ = "runs"

    id: str = Field(default_factory=_new_id, primary_key=True)
    kind: str = Field(index=True)  # 'analyze' | 'backtest'
    status: str = Field(default="running", index=True)  # 'running' | 'done' | 'error'

    created_at: datetime = Field(default_factory=_utcnow, index=True)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None

    error_message: str | None = None
    cost_usd: float | None = None

    # Config snapshot (the AnalyzeRequest / BacktestRequest fields)
    model_name: str
    model_provider: str
    tickers: list[str] = Field(sa_column=Column(JSON))
    start_date: str
    end_date: str
    initial_cash: float
    margin_requirement: float = 0.0
    selected_analysts: list[str] = Field(sa_column=Column(JSON))
    show_reasoning: bool = False

    # Multi-tenant placeholder (filled in F4+)
    created_by_token_id: str | None = None


class RunEvent(SQLModel, table=True):
    """SSE-shaped events emitted during a run. Powers replay."""

    __tablename__ = "run_events"

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(foreign_key="runs.id", index=True)
    seq: int
    ts: datetime = Field(default_factory=_utcnow)
    event_type: str
    payload: dict = Field(sa_column=Column(JSON))


class RunDecision(SQLModel, table=True):
    """Per-ticker final decision from the portfolio manager."""

    __tablename__ = "run_decisions"

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(foreign_key="runs.id", index=True)
    ticker: str
    action: str  # 'buy' | 'sell' | 'short' | 'cover' | 'hold'
    quantity: int
    confidence: float
    reasoning: str | None = None


class RunSignal(SQLModel, table=True):
    """Per-agent, per-ticker analyst signal."""

    __tablename__ = "run_signals"

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(foreign_key="runs.id", index=True)
    agent_name: str
    ticker: str
    signal: str | None = None  # 'bullish' | 'bearish' | 'neutral'
    confidence: float | None = None
    reasoning: dict | None = Field(default=None, sa_column=Column(JSON))
