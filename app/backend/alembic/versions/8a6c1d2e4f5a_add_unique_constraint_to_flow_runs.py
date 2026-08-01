"""Add unique constraint to hedge fund flow runs

Revision ID: 8a6c1d2e4f5a
Revises: d5e78f9a1b2c
Create Date: 2026-04-15 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8a6c1d2e4f5a"
down_revision: Union[str, None] = "d5e78f9a1b2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "hedge_fund_flow_runs" not in inspector.get_table_names():
        return

    existing_constraints = {
        constraint["name"] for constraint in inspector.get_unique_constraints("hedge_fund_flow_runs")
    }
    if "uq_flow_run_number" in existing_constraints:
        return

    # Normalize any duplicate run_number values so the new constraint can be created safely.
    rows = conn.execute(
        sa.text(
            """
            SELECT id, flow_id, run_number
            FROM hedge_fund_flow_runs
            ORDER BY flow_id, run_number, id
            """
        )
    ).fetchall()

    used_numbers: dict[int, set[int]] = {}
    max_numbers: dict[int, int] = {}

    for row in rows:
        flow_id = row.flow_id
        run_number = row.run_number or 0
        flow_used = used_numbers.setdefault(flow_id, set())
        current_max = max_numbers.get(flow_id, 0)

        if run_number > 0 and run_number not in flow_used:
            flow_used.add(run_number)
            max_numbers[flow_id] = max(current_max, run_number)
            continue

        next_run_number = max(current_max, max(flow_used, default=0)) + 1
        conn.execute(
            sa.text(
                """
                UPDATE hedge_fund_flow_runs
                SET run_number = :run_number
                WHERE id = :row_id
                """
            ),
            {"run_number": next_run_number, "row_id": row.id},
        )
        flow_used.add(next_run_number)
        max_numbers[flow_id] = next_run_number

    with op.batch_alter_table("hedge_fund_flow_runs") as batch_op:
        batch_op.create_unique_constraint("uq_flow_run_number", ["flow_id", "run_number"])


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "hedge_fund_flow_runs" not in inspector.get_table_names():
        return

    existing_constraints = {
        constraint["name"] for constraint in inspector.get_unique_constraints("hedge_fund_flow_runs")
    }
    if "uq_flow_run_number" not in existing_constraints:
        return

    with op.batch_alter_table("hedge_fund_flow_runs") as batch_op:
        batch_op.drop_constraint("uq_flow_run_number", type_="unique")
