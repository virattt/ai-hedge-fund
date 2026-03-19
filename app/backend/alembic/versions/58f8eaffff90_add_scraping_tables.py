"""add scraping tables

Revision ID: 58f8eaffff90
Revises: d5e78f9a1b2c
Create Date: 2026-03-14 18:03:37.431118

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58f8eaffff90'
down_revision: str | None = 'd5e78f9a1b2c'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema: create scraping_websites and scrape_results tables."""
    op.create_table(
        'scraping_websites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('scrape_status', sa.String(length=50), nullable=False),
        sa.Column('scrape_interval_minutes', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scraping_websites_id'), 'scraping_websites', ['id'], unique=False)

    op.create_table(
        'scrape_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('website_id', sa.Integer(), nullable=False),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('content_length', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['website_id'], ['scraping_websites.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scrape_results_id'), 'scrape_results', ['id'], unique=False)
    op.create_index(op.f('ix_scrape_results_website_id'), 'scrape_results', ['website_id'], unique=False)
    op.create_index('ix_scrape_results_website_id_scraped_at', 'scrape_results', ['website_id', 'scraped_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema: drop scrape_results then scraping_websites."""
    op.drop_index('ix_scrape_results_website_id_scraped_at', table_name='scrape_results')
    op.drop_index(op.f('ix_scrape_results_website_id'), table_name='scrape_results')
    op.drop_index(op.f('ix_scrape_results_id'), table_name='scrape_results')
    op.drop_table('scrape_results')
    op.drop_index(op.f('ix_scraping_websites_id'), table_name='scraping_websites')
    op.drop_table('scraping_websites')
