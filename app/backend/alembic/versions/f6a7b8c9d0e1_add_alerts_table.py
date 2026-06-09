"""add alerts table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-14 14:30:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: str | None = 'e5f6a7b8c9d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_type', sa.String(length=50), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='info'),
        sa.Column('sent_to_telegram', sa.Boolean(), server_default=sa.text('0'), nullable=True),
        sa.Column('telegram_error', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default=sa.text('0'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)
    op.create_index(op.f('ix_alerts_rule_type'), 'alerts', ['rule_type'], unique=False)
    op.create_index(op.f('ix_alerts_ticker'), 'alerts', ['ticker'], unique=False)
    op.create_index(op.f('ix_alerts_is_read'), 'alerts', ['is_read'], unique=False)
    op.create_index(op.f('ix_alerts_created_at'), 'alerts', ['created_at'], unique=False)
    op.create_index('ix_alerts_rule_ticker_created', 'alerts', ['rule_type', 'ticker', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_alerts_rule_ticker_created', table_name='alerts')
    op.drop_index(op.f('ix_alerts_created_at'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_is_read'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_ticker'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_rule_type'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_id'), table_name='alerts')
    op.drop_table('alerts')
