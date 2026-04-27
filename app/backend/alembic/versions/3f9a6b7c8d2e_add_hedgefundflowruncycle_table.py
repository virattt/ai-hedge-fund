"""Add HedgeFundFlowRunCycle table and update HedgeFundFlowRun

Revision ID: 3f9a6b7c8d2e
Revises: 2f8c5d9e4b1a
Create Date: 2024-11-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3f9a6b7c8d2e'
down_revision = '2f8c5d9e4b1a'
branch_labels = None
depends_on = None


def upgrade():
    # Get the database connection to check existing columns
    conn = op.get_bind()
    
    # Check if columns already exist before adding them
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('hedge_fund_flow_runs')]
    
    # Add new columns to hedge_fund_flow_runs table only if they don't exist
    if 'trading_mode' not in existing_columns:
        op.add_column('hedge_fund_flow_runs', sa.Column('trading_mode', sa.String(50), nullable=False, server_default='one-time'))
    if 'schedule' not in existing_columns:
        op.add_column('hedge_fund_flow_runs', sa.Column('schedule', sa.String(50), nullable=True))
    if 'duration' not in existing_columns:
        op.add_column('hedge_fund_flow_runs', sa.Column('duration', sa.String(50), nullable=True))
    if 'initial_portfolio' not in existing_columns:
        op.add_column('hedge_fund_flow_runs', sa.Column('initial_portfolio', sa.JSON, nullable=True))
    if 'final_portfolio' not in existing_columns:
        op.add_column('hedge_fund_flow_runs', sa.Column('final_portfolio', sa.JSON, nullable=True))
    
    # Create hedge_fund_flow_run_cycles table only if it doesn't exist
    existing_tables = inspector.get_table_names()
    if 'hedge_fund_flow_run_cycles' not in existing_tables:
        op.create_table(
            'hedge_fund_flow_run_cycles',
            sa.Column('id', sa.Integer, primary_key=True, index=True),
            sa.Column('flow_run_id', sa.Integer, nullable=False, index=True),
            sa.Column('cycle_number', sa.Integer, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('analyst_signals', sa.JSON, nullable=True),
            sa.Column('trading_decisions', sa.JSON, nullable=True),
            sa.Column('executed_trades', sa.JSON, nullable=True),
            sa.Column('portfolio_snapshot', sa.JSON, nullable=True),
            sa.Column('performance_metrics', sa.JSON, nullable=True),
            sa.Column('status', sa.String(50), nullable=False, server_default='IN_PROGRESS'),
            sa.Column('error_message', sa.Text, nullable=True),
            sa.Column('llm_calls_count', sa.Integer, nullable=True, server_default='0'),
            sa.Column('api_calls_count', sa.Integer, nullable=True, server_default='0'),
            sa.Column('estimated_cost', sa.String(20), nullable=True),
            sa.Column('trigger_reason', sa.String(100), nullable=True),
            sa.Column('market_conditions', sa.JSON, nullable=True),
        )
        
        # Create indexes for the new table
        op.create_index('ix_hedge_fund_flow_run_cycles_flow_run_id', 'hedge_fund_flow_run_cycles', ['flow_run_id'])
        op.create_index('ix_hedge_fund_flow_run_cycles_cycle_number', 'hedge_fund_flow_run_cycles', ['cycle_number'])
        op.create_index('ix_hedge_fund_flow_run_cycles_status', 'hedge_fund_flow_run_cycles', ['status'])
        op.create_index('ix_hedge_fund_flow_run_cycles_started_at', 'hedge_fund_flow_run_cycles', ['started_at'])


def downgrade():
    # Check if table exists before dropping
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'hedge_fund_flow_run_cycles' in existing_tables:
        # Drop indexes if they exist
        try:
            op.drop_index('ix_hedge_fund_flow_run_cycles_started_at', 'hedge_fund_flow_run_cycles')
            op.drop_index('ix_hedge_fund_flow_run_cycles_status', 'hedge_fund_flow_run_cycles')
            op.drop_index('ix_hedge_fund_flow_run_cycles_cycle_number', 'hedge_fund_flow_run_cycles')
            op.drop_index('ix_hedge_fund_flow_run_cycles_flow_run_id', 'hedge_fund_flow_run_cycles')
        except:
            pass  # Index may not exist
        
        # Drop hedge_fund_flow_run_cycles table
        op.drop_table('hedge_fund_flow_run_cycles')
    
    # Check existing columns before dropping
    existing_columns = [col['name'] for col in inspector.get_columns('hedge_fund_flow_runs')]
    
    # Remove columns from hedge_fund_flow_runs table only if they exist
    if 'final_portfolio' in existing_columns:
        op.drop_column('hedge_fund_flow_runs', 'final_portfolio')
    if 'initial_portfolio' in existing_columns:
        op.drop_column('hedge_fund_flow_runs', 'initial_portfolio')
    if 'duration' in existing_columns:
        op.drop_column('hedge_fund_flow_runs', 'duration')
    if 'schedule' in existing_columns:
        op.drop_column('hedge_fund_flow_runs', 'schedule')
    if 'trading_mode' in existing_columns:
        op.drop_column('hedge_fund_flow_runs', 'trading_mode') 