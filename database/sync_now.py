#!/usr/bin/env python3
"""
Sync new data from SQLite to PostgreSQL

This syncs:
1. New profirest matches (602 missing)
2. Updated coach names (enriched with full names)
3. All related data (lineups, goals, cards, subs)
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch

def sync_coaches():
    """Update coach names in PostgreSQL"""
    print("\n👔 Syncing coach names...")

    sqlite_conn = sqlite3.connect("fsv_archive_complete.db")
    sqlite_conn.row_factory = sqlite3.Row

    db_url = os.getenv("DATABASE_URL")
    pg_conn = psycopg2.connect(db_url)
    pg_cur = pg_conn.cursor()

    # Get coaches with full names from SQLite
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("""
        SELECT normalized_name, name, birth_date, birth_place
        FROM coaches
        WHERE name LIKE '% %'
    """)

    updated = 0
    for row in sqlite_cur.fetchall():
        norm_name, full_name, birth_date, birth_place = row

        # Update in PostgreSQL
        pg_cur.execute("""
            UPDATE coaches
            SET name = %s,
                birth_date = COALESCE(%s, birth_date),
                birth_place = COALESCE(%s, birth_place)
            WHERE normalized_name = %s
        """, (full_name, birth_date, birth_place, norm_name))

        if pg_cur.rowcount > 0:
            updated += 1

    pg_conn.commit()
    pg_conn.close()
    sqlite_conn.close()

    print(f"   ✓ Updated {updated} coach records with full names")
    return updated

def sync_profirest_matches():
    """Sync missing profirest matches"""
    print("\n⚽ Syncing profirest matches...")

    sqlite_conn = sqlite3.connect("fsv_archive_complete.db")
    sqlite_conn.row_factory = sqlite3.Row

    db_url = os.getenv("DATABASE_URL")
    pg_conn = psycopg2.connect(db_url)
    pg_cur = pg_conn.cursor()

    # Get existing match source_files from PostgreSQL
    pg_cur.execute("SELECT source_file FROM matches")
    existing = {row[0] for row in pg_cur.fetchall()}

    # Get profirest matches from SQLite
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("""
        SELECT source_file, match_date, home_team_id, away_team_id,
               home_score, away_score, halftime_home, halftime_away,
               attendance, kickoff_time
        FROM matches
        WHERE source_file LIKE '%profirest%'
    """)

    new_matches = []
    for row in sqlite_cur.fetchall():
        source_file = row[0]
        if source_file not in existing:
            new_matches.append(row)

    print(f"   Found {len(new_matches)} new profirest matches to sync")

    if new_matches:
        print("   ⚠️  Cannot sync matches without team ID mapping")
        print("   Recommendation: Use CSV export/import method")
        print()
        print("   Run these commands:")
        print("   1. sqlite3 fsv_archive_complete.db -csv -header \\")
        print("      'SELECT * FROM matches WHERE source_file LIKE \"%profirest%\"' > profirest_matches.csv")
        print()
        print("   2. # Adjust team IDs in CSV to match PostgreSQL")
        print()
        print("   3. psql $DATABASE_URL -c \"\\COPY matches FROM 'profirest_matches.csv' CSV HEADER\"")

    pg_conn.close()
    sqlite_conn.close()

    return len(new_matches)

def main():
    print("=" * 70)
    print("SYNC SQLITE → POSTGRESQL")
    print("=" * 70)

    if not os.getenv("DATABASE_URL"):
        print("❌ ERROR: DATABASE_URL not set")
        return

    # Sync coaches (safe - uses normalized_name)
    coach_count = sync_coaches()

    # Check profirest matches (needs team mapping)
    match_count = sync_profirest_matches()

    print("\n" + "=" * 70)
    print("SYNC SUMMARY")
    print("=" * 70)
    print(f"Coaches updated       : {coach_count}")
    print(f"Matches found         : {match_count}")
    print()
    print("✅ Coach names synced successfully!")
    print("⚠️  Profirest matches need manual sync (team ID mapping required)")
    print()
    print("See database/backups/ for SQL dumps or use CSV export method")

if __name__ == "__main__":
    main()
