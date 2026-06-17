"""Add price_estimate column to portfolio_analysis_results

Revision ID: 7a2b4c6d8e0f
Revises: add_watchlist_and_analysis_tables
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = "7a2b4c6d8e0f"
down_revision = None  # Safe to run independently
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portfolio_analysis_results",
        sa.Column("price_estimate", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portfolio_analysis_results", "price_estimate")
