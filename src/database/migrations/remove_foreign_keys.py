#!/usr/bin/env python3
"""
Script to automatically detect and remove all foreign key constraints from the database.

This script queries the database to find all foreign key constraints and drops them.
It's safer than running manual SQL because it discovers the constraint names automatically.

Usage:
    python remove_foreign_keys.py [--dry-run]

Options:
    --dry-run    Show what would be done without actually making changes
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path to import database modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from src.database.connection import SessionLocal, DB_NAME


def get_foreign_key_constraints(db):
    """
    Query the database to find all foreign key constraints.

    Returns:
        List of tuples: (table_name, constraint_name, column_name, referenced_table)
    """
    query = text("""
        SELECT
            TABLE_NAME,
            CONSTRAINT_NAME,
            COLUMN_NAME,
            REFERENCED_TABLE_NAME
        FROM
            INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE
            TABLE_SCHEMA = :schema_name
            AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY
            TABLE_NAME, CONSTRAINT_NAME
    """)

    result = db.execute(query, {"schema_name": DB_NAME})
    return [(row[0], row[1], row[2], row[3]) for row in result]


def drop_foreign_key(db, table_name, constraint_name, dry_run=False):
    """
    Drop a foreign key constraint from a table.

    Args:
        db: Database session
        table_name: Name of the table
        constraint_name: Name of the constraint to drop
        dry_run: If True, only print what would be done
    """
    drop_sql = f"ALTER TABLE `{table_name}` DROP FOREIGN KEY `{constraint_name}`"

    if dry_run:
        print(f"[DRY RUN] Would execute: {drop_sql}")
    else:
        try:
            db.execute(text(drop_sql))
            db.commit()
            print(f"✅ Dropped foreign key: {table_name}.{constraint_name}")
        except Exception as e:
            db.rollback()
            print(f"❌ Error dropping foreign key {table_name}.{constraint_name}: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Remove all foreign key constraints from the database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Automatically confirm without prompting"
    )
    args = parser.parse_args()

    print(f"{'='*70}")
    print(f"Foreign Key Removal Tool")
    print(f"Database: {DB_NAME}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print(f"{'='*70}\n")

    db = SessionLocal()

    try:
        # Step 1: Find all foreign keys
        print("Step 1: Discovering foreign key constraints...")
        foreign_keys = get_foreign_key_constraints(db)

        if not foreign_keys:
            print("✅ No foreign key constraints found in the database.")
            return

        print(f"Found {len(foreign_keys)} foreign key constraint(s):\n")

        # Group by table for better display
        fk_by_table = {}
        for table, constraint, column, ref_table in foreign_keys:
            if table not in fk_by_table:
                fk_by_table[table] = []
            fk_by_table[table].append((constraint, column, ref_table))

        for table, constraints in fk_by_table.items():
            print(f"  Table: {table}")
            for constraint, column, ref_table in constraints:
                print(f"    - {constraint}: {column} → {ref_table}")
            print()

        # Step 2: Drop foreign keys
        if not args.dry_run and not args.yes:
            response = input("Do you want to proceed with dropping these constraints? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ Cancelled by user.")
                return

        print("\nStep 2: Dropping foreign key constraints...")

        # Track already dropped constraints (to handle multi-column FKs)
        dropped_constraints = set()

        for table, constraint, column, ref_table in foreign_keys:
            if constraint not in dropped_constraints:
                drop_foreign_key(db, table, constraint, args.dry_run)
                dropped_constraints.add(constraint)

        print(f"\n{'='*70}")
        if args.dry_run:
            print("✅ Dry run completed. No changes were made.")
        else:
            print("✅ All foreign key constraints have been removed.")
        print(f"{'='*70}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
