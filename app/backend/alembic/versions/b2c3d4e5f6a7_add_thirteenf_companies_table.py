"""add thirteenf_companies table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-10 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create thirteenf_companies table for cached company list."""
    op.create_table(
        'thirteenf_companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company', sa.String(length=500), nullable=False),
        sa.Column('cik', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_thirteenf_companies_id'), 'thirteenf_companies', ['id'])
    op.create_index(op.f('ix_thirteenf_companies_company'), 'thirteenf_companies', ['company'])
    op.create_index(op.f('ix_thirteenf_companies_cik'), 'thirteenf_companies', ['cik'], unique=True)


def downgrade() -> None:
    """Drop thirteenf_companies table."""
    op.drop_index(op.f('ix_thirteenf_companies_cik'), table_name='thirteenf_companies')
    op.drop_index(op.f('ix_thirteenf_companies_company'), table_name='thirteenf_companies')
    op.drop_index(op.f('ix_thirteenf_companies_id'), table_name='thirteenf_companies')
    op.drop_table('thirteenf_companies')
