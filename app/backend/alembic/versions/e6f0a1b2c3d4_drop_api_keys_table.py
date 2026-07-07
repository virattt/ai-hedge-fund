"""drop_api_keys_table

Removes the api_keys table. API keys are now read exclusively from backend
environment variables (never stored in the database or entered in the UI), so the
table — which stored plaintext keys that were readable back over the API — is dropped.

Revision ID: e6f0a1b2c3d4
Revises: d5e78f9a1b2c
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f0a1b2c3d4'
down_revision: Union[str, None] = 'd5e78f9a1b2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the api_keys table if it exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'api_keys' in inspector.get_table_names():
        indexes = {ix['name'] for ix in inspector.get_indexes('api_keys')}
        if 'ix_api_keys_provider' in indexes:
            op.drop_index(op.f('ix_api_keys_provider'), table_name='api_keys')
        if 'ix_api_keys_id' in indexes:
            op.drop_index(op.f('ix_api_keys_id'), table_name='api_keys')
        op.drop_table('api_keys')


def downgrade() -> None:
    """Recreate the api_keys table (matches the original add_api_keys_table migration)."""
    op.create_table('api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('key_value', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_used', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider')
    )
    op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
    op.create_index(op.f('ix_api_keys_provider'), 'api_keys', ['provider'], unique=False)
