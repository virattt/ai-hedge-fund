"""initial: runs, run_events, run_decisions, run_signals

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-27

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401  (imported so SQLModel column types resolve)
from alembic import op


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("model_provider", sa.String(), nullable=False),
        sa.Column("tickers", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.String(), nullable=False),
        sa.Column("end_date", sa.String(), nullable=False),
        sa.Column("initial_cash", sa.Float(), nullable=False),
        sa.Column("margin_requirement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("selected_analysts", sa.JSON(), nullable=False),
        sa.Column("show_reasoning", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_token_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_kind", "runs", ["kind"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_created_at", "runs", ["created_at"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_run_events_run_id_seq", "run_events", ["run_id", "seq"])

    op.create_table(
        "run_decisions",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_run_decisions_run_id", "run_decisions", ["run_id"])

    op.create_table(
        "run_signals",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("signal", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_run_signals_run_id", "run_signals", ["run_id"])
    op.create_index("ix_run_signals_agent", "run_signals", ["run_id", "agent_name"])


def downgrade() -> None:
    op.drop_index("ix_run_signals_agent", table_name="run_signals")
    op.drop_index("ix_run_signals_run_id", table_name="run_signals")
    op.drop_table("run_signals")

    op.drop_index("ix_run_decisions_run_id", table_name="run_decisions")
    op.drop_table("run_decisions")

    op.drop_index("ix_run_events_run_id_seq", table_name="run_events")
    op.drop_table("run_events")

    op.drop_index("ix_runs_created_at", table_name="runs")
    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_kind", table_name="runs")
    op.drop_table("runs")
