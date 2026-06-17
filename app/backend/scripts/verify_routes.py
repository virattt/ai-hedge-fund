"""Route verification script.

Checks that all required API endpoints and DB tables exist.
Run before or after starting the server to catch stale-code issues.

Usage:
    python -m app.backend.scripts.verify_routes
"""

import sys
from sqlalchemy import inspect

from app.backend.database.connection import engine
from app.backend.main import app

REQUIRED_ROUTES = [
    ("POST", "/portfolio/analyze"),
    ("GET", "/portfolio/analyze/{job_id}"),
    ("GET", "/portfolio/analysis/latest"),
    ("GET", "/watchlist"),
    ("POST", "/watchlist"),
    ("POST", "/watchlist/analyze"),
    ("GET", "/watchlist/analysis/latest"),
    ("POST", "/holdings/import-csv"),
    ("GET", "/holdings"),
    ("GET", "/dashboard"),
]

REQUIRED_TABLES = [
    "holdings",
    "watchlist",
    "portfolio_analysis_results",
    "analysis_jobs",
]


def verify():
    errors = []

    # Check routes
    registered = set()
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                registered.add((method, route.path))

    print("[ROUTES] Checking required endpoints...")
    for method, path in REQUIRED_ROUTES:
        if (method, path) in registered:
            print(f"  OK  {method:6} {path}")
        else:
            print(f"  MISS {method:6} {path}")
            errors.append(f"Missing route: {method} {path}")

    # Check DB tables
    print("\n[DB] Checking required tables...")
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    for table in REQUIRED_TABLES:
        if table in existing:
            cols = len(inspector.get_columns(table))
            print(f"  OK  {table} ({cols} columns)")
        else:
            print(f"  MISS {table}")
            errors.append(f"Missing table: {table}")

    # Summary
    print("")
    if errors:
        print(f"[VERIFY] FAILED — {len(errors)} issue(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("[VERIFY] ALL CHECKS PASSED")


if __name__ == "__main__":
    verify()
