"""add depth crawling columns

Revision ID: a1b2c3d4e5f6
Revises: 58f8eaffff90
Create Date: 2026-03-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '58f8eaffff90'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add depth crawling columns to scraping_websites and scrape_results."""
    # ScrapingWebsite — 3 new columns
    op.add_column('scraping_websites', sa.Column('max_depth', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('scraping_websites', sa.Column('max_pages', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('scraping_websites', sa.Column('include_external', sa.Boolean(), nullable=False, server_default='0'))

    # ScrapeResult — 4 new columns
    op.add_column('scrape_results', sa.Column('page_url', sa.String(length=2048), nullable=True))
    op.add_column('scrape_results', sa.Column('depth', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scrape_results', sa.Column('parent_result_id', sa.Integer(), nullable=True))
    op.add_column('scrape_results', sa.Column('scrape_run_id', sa.String(length=36), nullable=True))

    with op.batch_alter_table('scrape_results') as batch_op:
        batch_op.create_foreign_key('fk_scrape_results_parent', 'scrape_results', ['parent_result_id'], ['id'])
    op.create_index('ix_scrape_results_scrape_run_id', 'scrape_results', ['scrape_run_id'], unique=False)


def downgrade() -> None:
    """Remove depth crawling columns."""
    op.drop_index('ix_scrape_results_scrape_run_id', table_name='scrape_results')
    with op.batch_alter_table('scrape_results') as batch_op:
        batch_op.drop_constraint('fk_scrape_results_parent', type_='foreignkey')

    op.drop_column('scrape_results', 'scrape_run_id')
    op.drop_column('scrape_results', 'parent_result_id')
    op.drop_column('scrape_results', 'depth')
    op.drop_column('scrape_results', 'page_url')

    op.drop_column('scraping_websites', 'include_external')
    op.drop_column('scraping_websites', 'max_pages')
    op.drop_column('scraping_websites', 'max_depth')
