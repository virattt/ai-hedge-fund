"""Database initialization script.

Creates all tables defined in models.py. Adds missing columns to existing
tables (handles the SQLite limitation where create_all won't ALTER).

Usage:
    python -m app.backend.scripts.db_init
    python -m app.backend.scripts.db_init --reset   (drops and recreates all tables)
"""

import sys
from sqlalchemy import inspect, text

from app.backend.database.connection import engine, Base
from app.backend.database.models import (
    HedgeFundFlow, HedgeFundFlowRun, HedgeFundFlowRunCycle,
    Account, Holding, Watchlist, PortfolioAnalysisResult, AnalysisJob, ApiKey,
)

EXPECTED_COLUMNS = {
    "holdings": {
        "account_id": "INTEGER REFERENCES accounts(id)",
        "sector": "VARCHAR(200)",
    },
}

REQUIRED_TABLES = [
    "holdings",
    "watchlist",
    "portfolio_analysis_results",
    "analysis_jobs",
    "accounts",
    "api_keys",
    "hedge_fund_flows",
    "hedge_fund_flow_runs",
    "hedge_fund_flow_run_cycles",
]


def init_db(reset: bool = False):
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if reset:
        print("[DB] Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        existing_tables = []

    # Create tables that don't exist
    print("[DB] Running create_all...")
    Base.metadata.create_all(bind=engine)

    # Add missing columns to existing tables (SQLite ALTER TABLE)
    for table_name, columns in EXPECTED_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for col_name, col_def in columns.items():
            if col_name not in existing_cols:
                stmt = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                print(f"[DB] Adding column: {table_name}.{col_name}")
                with engine.connect() as conn:
                    conn.execute(text(stmt))
                    conn.commit()

    # Final verification
    inspector = inspect(engine)
    final_tables = set(inspector.get_table_names())
    missing = [t for t in REQUIRED_TABLES if t not in final_tables]

    if missing:
        print(f"[DB] ERROR: Missing tables: {missing}")
        sys.exit(1)

    print(f"[DB] OK — {len(final_tables)} tables present")
    for t in sorted(REQUIRED_TABLES):
        cols = [c["name"] for c in inspector.get_columns(t)]
        print(f"  {t}: {len(cols)} columns")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    if reset:
        confirm = input("[DB] WARNING: --reset will delete ALL data. Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            print("[DB] Aborted.")
            sys.exit(0)
    init_db(reset=reset)
