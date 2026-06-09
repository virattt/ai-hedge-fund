"""add spinoff_filings table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-14 12:30:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: str | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('spinoff_filings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('accession_no', sa.String(length=50), nullable=False),
        sa.Column('cik', sa.Integer(), nullable=False),
        sa.Column('company', sa.String(length=500), nullable=False),
        sa.Column('form', sa.String(length=20), nullable=False),
        sa.Column('filing_date', sa.String(length=10), nullable=False),
        sa.Column('primary_doc_url', sa.String(length=500), nullable=True),
        sa.Column('primary_doc_description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('accession_no'),
    )
    op.create_index(op.f('ix_spinoff_filings_id'), 'spinoff_filings', ['id'], unique=False)
    op.create_index(op.f('ix_spinoff_filings_accession_no'), 'spinoff_filings', ['accession_no'], unique=False)
    op.create_index(op.f('ix_spinoff_filings_cik'), 'spinoff_filings', ['cik'], unique=False)
    op.create_index(op.f('ix_spinoff_filings_company'), 'spinoff_filings', ['company'], unique=False)
    op.create_index(op.f('ix_spinoff_filings_form'), 'spinoff_filings', ['form'], unique=False)
    op.create_index(op.f('ix_spinoff_filings_filing_date'), 'spinoff_filings', ['filing_date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_spinoff_filings_filing_date'), table_name='spinoff_filings')
    op.drop_index(op.f('ix_spinoff_filings_form'), table_name='spinoff_filings')
    op.drop_index(op.f('ix_spinoff_filings_company'), table_name='spinoff_filings')
    op.drop_index(op.f('ix_spinoff_filings_cik'), table_name='spinoff_filings')
    op.drop_index(op.f('ix_spinoff_filings_accession_no'), table_name='spinoff_filings')
    op.drop_index(op.f('ix_spinoff_filings_id'), table_name='spinoff_filings')
    op.drop_table('spinoff_filings')
