#!/usr/bin/env python3
"""Check PostgreSQL sync status against the local SQLite source of truth."""

import sqlite3
import re
from typing import Iterable

from psycopg2 import sql

from config import Config


def _select_count(cursor, table_name: str) -> int:
    cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
    return cursor.fetchone()[0]


def _select_sqlite_count(cursor, table_name: str) -> int:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise ValueError(f"Invalid SQLite identifier: {table_name}")
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")  # nosec B608 - identifier is validated above
    return cursor.fetchone()[0]


def _print_table_counts(cursor, tables: list[str], table_names: Iterable[str]) -> None:
    for table_name in table_names:
        if table_name in tables:
            count = _select_count(cursor, table_name)
            print(f"   ✓ {table_name:20s}: {count:>6,} records")
        else:
            print(f"   ✗ {table_name:20s}: NOT FOUND")

def main():
    config = Config()

    if not config.PG_ENABLED:
        print("❌ PostgreSQL is not enabled")
        print("   Set DATABASE_URL or DB_URL in .env")
        return

    try:
        import psycopg2

        dsn = config.build_psycopg2_dsn()
        print(f"🔌 Connecting to PostgreSQL...")
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()

        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]

        print(f"\n✅ Connected successfully!")
        print(f"📋 Found {len(tables)} tables in public schema\n")

        core_tables = ['teams', 'players', 'coaches', 'matches', 'goals', 'cards']

        for table in core_tables:
            if table in tables:
                count = _select_count(cur, table)
                print(f"   ✓ {table:20s}: {count:>6,} records")

                if table == 'matches':
                    cur.execute("SELECT COUNT(*) FROM matches WHERE source_file LIKE '%profirest%'")
                    profirest = cur.fetchone()[0]
                    print(f"     → Profirest matches  : {profirest:>6,}")

                if table == 'players':
                    cur.execute("SELECT COUNT(*) FROM players WHERE name LIKE '% %'")
                    full_names = cur.fetchone()[0]
                    print(f"     → With full names    : {full_names:>6,}")

                if table == 'coaches':
                    cur.execute("SELECT COUNT(*) FROM coaches WHERE name LIKE '% %'")
                    full_names = cur.fetchone()[0]
                    print(f"     → With full names    : {full_names:>6,}")
            else:
                print(f"   ✗ {table:20s}: NOT FOUND")

        print(f"\n📱 Application tables:")
        app_tables = ['quiz_games', 'quiz_questions', 'chat_sessions', 'chat_messages']
        _print_table_counts(cur, tables, app_tables)

        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'MATERIALIZED VIEW'
            ORDER BY table_name
        """)
        views = [row[0] for row in cur.fetchall()]

        if views:
            print(f"\n📊 Materialized views:")
            for view in views:
                print(f"   ✓ {view}")

        print(f"\n" + "="*70)
        print("COMPARISON: SQLite vs PostgreSQL")
        print("="*70)

        sqlite_conn = sqlite3.connect(str(config.DATABASE_PATH))
        sqlite_cur = sqlite_conn.cursor()

        conn2 = psycopg2.connect(dsn)
        cur2 = conn2.cursor()

        for table in core_tables:
            if table in tables:
                sqlite_count = _select_sqlite_count(sqlite_cur, table)

                pg_count = _select_count(cur2, table)

                diff = sqlite_count - pg_count
                status = "✅" if diff == 0 else "⚠️ "

                print(f"{status} {table:15s}: SQLite={sqlite_count:>6,}  PostgreSQL={pg_count:>6,}  Diff={diff:>6,}")

        sqlite_conn.close()
        conn.close()
        conn2.close()
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        import logging

        logging.exception("Status check failed")


if __name__ == '__main__':
    main()

