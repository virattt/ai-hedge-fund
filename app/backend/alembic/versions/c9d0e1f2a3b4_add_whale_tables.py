"""add whale_funds + whale_entry_cache tables

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-05-16 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d0e1f2a3b4'
down_revision: str | None = 'b8c9d0e1f2a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('whale_funds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cik', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cik'),
    )
    op.create_index(op.f('ix_whale_funds_id'), 'whale_funds', ['id'], unique=False)
    op.create_index(op.f('ix_whale_funds_cik'), 'whale_funds', ['cik'], unique=True)

    op.create_table('whale_entry_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('whale_cik', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('entry_quarter_label', sa.String(length=20), nullable=True),
        sa.Column('entry_period_start', sa.String(length=20), nullable=True),
        sa.Column('entry_period_end', sa.String(length=20), nullable=True),
        sa.Column('entry_vwap', sa.Float(), nullable=True),
        sa.Column('entry_low', sa.Float(), nullable=True),
        sa.Column('entry_high', sa.Float(), nullable=True),
        sa.Column('share_count_at_entry', sa.Float(), nullable=True),
        sa.Column('is_pre_lookback', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_whale_entry_cache_id'), 'whale_entry_cache', ['id'], unique=False)
    op.create_index(op.f('ix_whale_entry_cache_whale_cik'), 'whale_entry_cache', ['whale_cik'], unique=False)
    op.create_index(op.f('ix_whale_entry_cache_ticker'), 'whale_entry_cache', ['ticker'], unique=False)
    op.create_index('ix_whale_entry_cache_whale_ticker', 'whale_entry_cache', ['whale_cik', 'ticker'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_whale_entry_cache_whale_ticker', table_name='whale_entry_cache')
    op.drop_index(op.f('ix_whale_entry_cache_ticker'), table_name='whale_entry_cache')
    op.drop_index(op.f('ix_whale_entry_cache_whale_cik'), table_name='whale_entry_cache')
    op.drop_index(op.f('ix_whale_entry_cache_id'), table_name='whale_entry_cache')
    op.drop_table('whale_entry_cache')

    op.drop_index(op.f('ix_whale_funds_cik'), table_name='whale_funds')
    op.drop_index(op.f('ix_whale_funds_id'), table_name='whale_funds')
    op.drop_table('whale_funds')
