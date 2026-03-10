#!/usr/bin/env python3
"""
Complete SQLite to PostgreSQL Sync for FSV Mainz 05 Archive.

Syncs ALL data from fsv_archive_complete.db to Neon PostgreSQL.

Usage:
    python database/sync_sqlite_to_postgres.py --dry-run
    python database/sync_sqlite_to_postgres.py
"""

import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from database.sync_plan import SYNC_TABLE_STEPS

# Database paths (override via env: SQLITE_DB, DATABASE_URL or DB_URL)
SQLITE_PATH = os.getenv("SQLITE_DB", "fsv_archive_complete.db")
POSTGRES_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL") or ""


class SyncEngine:
    """Syncs SQLite database to PostgreSQL."""

    def __init__(self, sqlite_path: str, pg_url: str, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats: Dict[str, int] = {}

        # Connect to SQLite
        self.sqlite_conn = sqlite3.connect(sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row

        # Connect to PostgreSQL
        self.pg_conn = psycopg2.connect(pg_url)
        self.pg_conn.autocommit = False

        # ID mappings (SQLite ID -> Postgres ID)
        self.id_maps: Dict[str, Dict[int, int]] = {
            'teams': {},
            'competitions': {},
            'seasons': {},
            'season_competitions': {},
            'referees': {},
            'coaches': {},
            'players': {},
            'matches': {},
        }

    def close(self):
        """Close database connections."""
        self.sqlite_conn.close()
        self.pg_conn.close()

    @staticmethod
    def _validate_identifier(identifier: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
            raise ValueError(f"Invalid SQL identifier: {identifier}")
        return identifier

    def _build_sqlite_select(self, table_name: str, all_columns: List[str]) -> str:
        validated_table = self._validate_identifier(table_name)
        validated_columns = [self._validate_identifier(column) for column in all_columns]
        return f"SELECT {', '.join(validated_columns)} FROM {validated_table}"  # nosec B608 - identifiers are validated above

    def _build_insert_sql(self, table_name: str, columns: List[str], id_column: str) -> sql.Composed:
        return sql.SQL(
            """
            INSERT INTO {table} ({columns})
            VALUES %s
            RETURNING {id_column}
            """
        ).format(
            table=sql.Identifier(self._validate_identifier(table_name)),
            columns=sql.SQL(", ").join(sql.Identifier(self._validate_identifier(column)) for column in columns),
            id_column=sql.Identifier(self._validate_identifier(id_column)),
        )

    def sync_table(self, table_name: str, columns: List[str], id_column: str,
                   fk_mappings: Dict[str, str] = None):
        """
        Generic table sync with ID mapping and foreign key handling.

        Args:
            table_name: Name of the table
            columns: List of columns to sync (excluding auto-increment ID)
            id_column: Name of the primary key column
            fk_mappings: Dict mapping column names to their reference table for ID remapping
        """
        print(f"\n{'='*60}")
        print(f"Syncing {table_name}...")

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get all rows from SQLite
        all_cols = [id_column] + columns
        sqlite_cur.execute(self._build_sqlite_select(table_name, all_cols))
        rows = sqlite_cur.fetchall()

        if not rows:
            print(f"  No data in {table_name}")
            self.stats[table_name] = 0
            return

        # Process rows with FK remapping
        processed_rows = []
        for row in rows:
            sqlite_id = row[0]
            values = list(row[1:])

            # Remap foreign keys if needed
            if fk_mappings:
                for i, col in enumerate(columns):
                    if col in fk_mappings and values[i] is not None:
                        ref_table = fk_mappings[col]
                        old_id = values[i]
                        if old_id in self.id_maps[ref_table]:
                            values[i] = self.id_maps[ref_table][old_id]
                        else:
                            # FK reference not found - set to NULL or skip
                            values[i] = None

            processed_rows.append((sqlite_id, values))

        if self.dry_run:
            print(f"  Would insert {len(processed_rows)} rows")
            self.stats[table_name] = len(processed_rows)
            # Create dummy ID mappings for dry run
            for sqlite_id, _ in processed_rows:
                self.id_maps.setdefault(table_name, {})[sqlite_id] = sqlite_id
            return

        # Insert into PostgreSQL and capture new IDs
        insert_sql = self._build_insert_sql(table_name, columns, id_column)

        # Use execute_values for batch insert
        values_list = [tuple(row[1]) for row in processed_rows]

        try:
            # Insert in batches
            batch_size = 1000
            inserted_ids = []

            for i in range(0, len(values_list), batch_size):
                batch = values_list[i:i+batch_size]
                result = execute_values(
                    pg_cur,
                    insert_sql,
                    batch,
                    template=None,
                    page_size=batch_size,
                    fetch=True
                )
                inserted_ids.extend([r[0] for r in result])

            # Build ID mapping
            for (sqlite_id, _), pg_id in zip(processed_rows, inserted_ids):
                self.id_maps.setdefault(table_name, {})[sqlite_id] = pg_id

            self.stats[table_name] = len(processed_rows)
            print(f"  Inserted {len(processed_rows)} rows")

        except Exception as e:
            print(f"  ERROR: {e}")
            raise

    def sync_all(self):
        """Run complete sync in dependency order."""
        print("=" * 70)
        print("FSV MAINZ 05 ARCHIVE - SQLITE TO POSTGRESQL SYNC")
        print("=" * 70)

        if self.dry_run:
            print("\n*** DRY RUN MODE - No changes will be made ***\n")

        try:
            for table_name, columns, id_column, fk_mappings in SYNC_TABLE_STEPS:
                self.sync_table(table_name, columns, id_column, fk_mappings)

            # Commit or rollback
            if self.dry_run:
                self.pg_conn.rollback()
                print("\n*** DRY RUN COMPLETE - No changes made ***")
            else:
                self.pg_conn.commit()
                print("\n*** SYNC COMPLETE - All changes committed ***")

            # Print summary
            self.print_summary()

        except Exception as e:
            self.pg_conn.rollback()
            print(f"\n*** ERROR: {e} ***")
            print("*** All changes rolled back ***")
            raise

    def print_summary(self):
        """Print sync summary."""
        print("\n" + "=" * 70)
        print("SYNC SUMMARY")
        print("=" * 70)

        total = 0
        for table, count in self.stats.items():
            print(f"  {table:25s}: {count:>8,} rows")
            total += count

        print("-" * 45)
        print(f"  {'TOTAL':25s}: {total:>8,} rows")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync SQLite to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Preview without syncing")
    parser.add_argument("--sqlite", default=SQLITE_PATH, help="SQLite database path")
    args = parser.parse_args()

    if not os.path.exists(args.sqlite):
        print(f"ERROR: SQLite database not found: {args.sqlite}")
        return 1

    pg_url = POSTGRES_URL or os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if not pg_url:
        print("Error: set DATABASE_URL or DB_URL in .env")
        return 1
    engine = SyncEngine(args.sqlite, pg_url, dry_run=args.dry_run)

    try:
        engine.sync_all()
    finally:
        engine.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
