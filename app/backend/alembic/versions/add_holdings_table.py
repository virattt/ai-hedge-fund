"""add_holdings_table

Revision ID: e6f89a2b3c4d
Revises: d5e78f9a1b2c
Create Date: 2026-05-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f89a2b3c4d'
down_revision: Union[str, None] = 'd5e78f9a1b2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('holdings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('portfolio_name', sa.String(length=200), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('investment_name', sa.String(length=300), nullable=False),
        sa.Column('quantity', sa.String(length=50), nullable=False),
        sa.Column('buy_price', sa.String(length=50), nullable=False),
        sa.Column('cost_basis', sa.String(length=50), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_holdings_id'), 'holdings', ['id'], unique=False)
    op.create_index(op.f('ix_holdings_ticker'), 'holdings', ['ticker'], unique=False)
    op.create_index(op.f('ix_holdings_portfolio_name'), 'holdings', ['portfolio_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_holdings_portfolio_name'), table_name='holdings')
    op.drop_index(op.f('ix_holdings_ticker'), table_name='holdings')
    op.drop_index(op.f('ix_holdings_id'), table_name='holdings')
    op.drop_table('holdings')
