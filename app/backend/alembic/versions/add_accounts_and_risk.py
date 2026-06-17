"""Add accounts table and extend holdings with account_id and sector

Revision ID: 7a2b3c4d5e6f
Revises: add_holdings_table
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = '7a2b3c4d5e6f'
down_revision = 'add_holdings_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('owner_name', sa.String(200), nullable=False, index=True),
        sa.Column('account_type', sa.String(100), nullable=False, server_default='ISA'),
        sa.Column('provider', sa.String(200), nullable=False, server_default='AJ Bell'),
        sa.Column('label', sa.String(300), nullable=True),
    )

    with op.batch_alter_table('holdings') as batch_op:
        batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sector', sa.String(200), nullable=True))
        batch_op.create_foreign_key('fk_holdings_account_id', 'accounts', ['account_id'], ['id'])
        batch_op.create_index('ix_holdings_account_id', ['account_id'])


def downgrade() -> None:
    with op.batch_alter_table('holdings') as batch_op:
        batch_op.drop_index('ix_holdings_account_id')
        batch_op.drop_constraint('fk_holdings_account_id', type_='foreignkey')
        batch_op.drop_column('sector')
        batch_op.drop_column('account_id')

    op.drop_table('accounts')
