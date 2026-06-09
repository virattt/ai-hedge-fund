"""add discovery_snapshots table

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-15 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c9d0e1f2a3'
down_revision: str | None = 'a7b8c9d0e1f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('discovery_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('cik', sa.Integer(), nullable=True),
        sa.Column('is_ticker', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('company', sa.String(length=500), nullable=True),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('distinct_sources', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('signals', sa.JSON(), nullable=True),
        sa.Column('snapshot_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_discovery_snapshots_id'), 'discovery_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_discovery_snapshots_ticker'), 'discovery_snapshots', ['ticker'], unique=False)
    op.create_index(op.f('ix_discovery_snapshots_cik'), 'discovery_snapshots', ['cik'], unique=False)
    op.create_index(op.f('ix_discovery_snapshots_snapshot_at'), 'discovery_snapshots', ['snapshot_at'], unique=False)
    op.create_index('ix_discovery_snapshots_ticker_at', 'discovery_snapshots', ['ticker', 'snapshot_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_discovery_snapshots_ticker_at', table_name='discovery_snapshots')
    op.drop_index(op.f('ix_discovery_snapshots_snapshot_at'), table_name='discovery_snapshots')
    op.drop_index(op.f('ix_discovery_snapshots_cik'), table_name='discovery_snapshots')
    op.drop_index(op.f('ix_discovery_snapshots_ticker'), table_name='discovery_snapshots')
    op.drop_index(op.f('ix_discovery_snapshots_id'), table_name='discovery_snapshots')
    op.drop_table('discovery_snapshots')
