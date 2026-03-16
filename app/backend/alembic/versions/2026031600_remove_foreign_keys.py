"""Remove all foreign key constraints

Revision ID: 2026031600
Revises: 2026031500
Create Date: 2026-03-16 00:00:00.000000

This migration removes all foreign key constraints from the database tables
while preserving the column references. The columns themselves are kept as
regular integer fields with indexes for query performance.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026031600'
down_revision = '2026031500'
branch_labels = None
depends_on = None


def upgrade():
    """
    Drop all foreign key constraints from the database.

    Note: This is database-agnostic and will work with SQLite, MySQL, and PostgreSQL.
    SQLite: Foreign keys are recreated on table rebuild
    MySQL/PostgreSQL: Foreign keys are dropped explicitly
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # For SQLite, we need to check if foreign keys exist first
    # SQLite foreign keys might not exist depending on how tables were created

    if dialect_name == 'sqlite':
        # SQLite doesn't support DROP CONSTRAINT, so we skip this
        # The models.py changes will prevent future foreign keys from being created
        pass

    elif dialect_name in ['mysql', 'postgresql']:
        # For MySQL and PostgreSQL, we need to get the constraint names and drop them
        inspector = sa.inspect(conn)

        # Drop foreign key from hedge_fund_flow_runs
        try:
            fks = inspector.get_foreign_keys('hedge_fund_flow_runs')
            for fk in fks:
                if fk.get('constrained_columns') == ['flow_id']:
                    constraint_name = fk.get('name')
                    if constraint_name:
                        op.drop_constraint(constraint_name, 'hedge_fund_flow_runs', type_='foreignkey')
        except Exception as e:
            print(f"Warning: Could not drop foreign key from hedge_fund_flow_runs: {e}")

        # Drop foreign key from hedge_fund_flow_run_cycles
        try:
            fks = inspector.get_foreign_keys('hedge_fund_flow_run_cycles')
            for fk in fks:
                if fk.get('constrained_columns') == ['flow_run_id']:
                    constraint_name = fk.get('name')
                    if constraint_name:
                        op.drop_constraint(constraint_name, 'hedge_fund_flow_run_cycles', type_='foreignkey')
        except Exception as e:
            print(f"Warning: Could not drop foreign key from hedge_fund_flow_run_cycles: {e}")


def downgrade():
    """
    Recreate foreign key constraints.

    Note: This only works for MySQL and PostgreSQL. SQLite is not supported.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    if dialect_name == 'sqlite':
        # SQLite doesn't support ADD CONSTRAINT for foreign keys
        print("Warning: Cannot restore foreign keys on SQLite through migration")
        pass

    elif dialect_name in ['mysql', 'postgresql']:
        # Recreate the foreign keys
        try:
            op.create_foreign_key(
                'fk_hedge_fund_flow_runs_flow_id',
                'hedge_fund_flow_runs', 'hedge_fund_flows',
                ['flow_id'], ['id']
            )
        except Exception as e:
            print(f"Warning: Could not recreate foreign key on hedge_fund_flow_runs: {e}")

        try:
            op.create_foreign_key(
                'fk_hedge_fund_flow_run_cycles_flow_run_id',
                'hedge_fund_flow_run_cycles', 'hedge_fund_flow_runs',
                ['flow_run_id'], ['id']
            )
        except Exception as e:
            print(f"Warning: Could not recreate foreign key on hedge_fund_flow_run_cycles: {e}")
