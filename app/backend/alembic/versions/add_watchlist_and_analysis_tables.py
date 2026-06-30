"""Add watchlist, portfolio_analysis_results, and analysis_jobs tables

Revision ID: a1b2c3d4e5f6
Revises: add_holdings_table
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = 'add_holdings_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'watchlist',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ticker', sa.String(20), nullable=False, index=True),
        sa.Column('investment_name', sa.String(300), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    op.create_table(
        'portfolio_analysis_results',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('holding_id', sa.Integer(), sa.ForeignKey('holdings.id'), nullable=True, index=True),
        sa.Column('watchlist_id', sa.Integer(), sa.ForeignKey('watchlist.id'), nullable=True, index=True),
        sa.Column('ticker', sa.String(20), nullable=False, index=True),
        sa.Column('analysis_ticker', sa.String(20), nullable=False),
        sa.Column('final_action', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('technical_summary', sa.Text(), nullable=True),
        sa.Column('fundamental_summary', sa.Text(), nullable=True),
        sa.Column('sentiment_summary', sa.Text(), nullable=True),
        sa.Column('valuation_summary', sa.Text(), nullable=True),
        sa.Column('risk_summary', sa.Text(), nullable=True),
        sa.Column('portfolio_manager_summary', sa.Text(), nullable=True),
        sa.Column('positive_factors', sa.Text(), nullable=True),
        sa.Column('risk_factors', sa.Text(), nullable=True),
        sa.Column('uncertainties', sa.Text(), nullable=True),
    )

    op.create_table(
        'analysis_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('total_tickers', sa.Integer(), nullable=True),
        sa.Column('completed_tickers', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_ids', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('analysis_jobs')
    op.drop_table('portfolio_analysis_results')
    op.drop_table('watchlist')
