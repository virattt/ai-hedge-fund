"""add thirteenf_saved_selections table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-10 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create thirteenf_saved_selections table."""
    op.create_table(
        'thirteenf_saved_selections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cik', sa.Integer(), nullable=False),
        sa.Column('company', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_thirteenf_saved_selections_id'), 'thirteenf_saved_selections', ['id'])
    op.create_index(op.f('ix_thirteenf_saved_selections_cik'), 'thirteenf_saved_selections', ['cik'], unique=True)


def downgrade() -> None:
    """Drop thirteenf_saved_selections table."""
    op.drop_index(op.f('ix_thirteenf_saved_selections_cik'), table_name='thirteenf_saved_selections')
    op.drop_index(op.f('ix_thirteenf_saved_selections_id'), table_name='thirteenf_saved_selections')
    op.drop_table('thirteenf_saved_selections')
