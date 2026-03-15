"""add_cache_tables

Revision ID: 2026031500
Revises: d5e78f9a1b2c
Create Date: 2026-03-15 17:10:00.000000

Adds MySQL cache layer tables for stock prices, financial metrics, and company news.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '2026031500'
down_revision = 'd5e78f9a1b2c'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create cache tables for stock prices, financial metrics, and company news.

    These tables use the backend database (SQLite for dev) but are designed
    for MySQL/PostgreSQL in production.
    """
    # stock_prices table
    op.create_table(
        'stock_prices',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('time', sa.DateTime(), nullable=False),
        sa.Column('open', sa.DECIMAL(precision=20, scale=6), nullable=True),
        sa.Column('close', sa.DECIMAL(precision=20, scale=6), nullable=True),
        sa.Column('high', sa.DECIMAL(precision=20, scale=6), nullable=True),
        sa.Column('low', sa.DECIMAL(precision=20, scale=6), nullable=True),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.Column('data_source', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_stock_prices_ticker_date', 'stock_prices', ['ticker', 'date'], unique=False)
    op.create_index('uk_stock_prices_ticker_time', 'stock_prices', ['ticker', 'time'], unique=True)

    # financial_metrics table
    op.create_table(
        'financial_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('report_period', sa.Date(), nullable=False),
        sa.Column('period', sa.String(length=20), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('market_cap', sa.DECIMAL(precision=20, scale=2), nullable=True),
        sa.Column('pe_ratio', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('pb_ratio', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('ps_ratio', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('revenue', sa.DECIMAL(precision=20, scale=2), nullable=True),
        sa.Column('net_income', sa.DECIMAL(precision=20, scale=2), nullable=True),
        sa.Column('metrics_json', sa.JSON(), nullable=True),
        sa.Column('data_source', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uk_financial_metrics_ticker_period', 'financial_metrics', ['ticker', 'report_period', 'period'], unique=True)

    # company_news table
    op.create_table(
        'company_news',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('data_source', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_company_news_ticker_date', 'company_news', ['ticker', 'date'], unique=False)


def downgrade():
    """Drop cache tables."""
    op.drop_table('company_news')
    op.drop_table('financial_metrics')
    op.drop_table('stock_prices')
