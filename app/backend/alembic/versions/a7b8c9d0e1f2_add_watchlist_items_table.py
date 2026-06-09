"""add watchlist_items table

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-14 16:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: str | None = 'f6a7b8c9d0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('watchlist_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('last_analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_overall_sentiment', sa.String(length=20), nullable=True),
        sa.Column('last_delta_direction', sa.String(length=20), nullable=True),
        sa.Column('last_management_tone', sa.String(length=200), nullable=True),
        sa.Column('last_payload', sa.JSON(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker'),
    )
    op.create_index(op.f('ix_watchlist_items_id'), 'watchlist_items', ['id'], unique=False)
    op.create_index(op.f('ix_watchlist_items_ticker'), 'watchlist_items', ['ticker'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_watchlist_items_ticker'), table_name='watchlist_items')
    op.drop_index(op.f('ix_watchlist_items_id'), table_name='watchlist_items')
    op.drop_table('watchlist_items')
