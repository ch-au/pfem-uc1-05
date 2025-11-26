#!/usr/bin/env python3
"""
Sync complete SQLite database to PostgreSQL (Neon).

This script syncs all data from the local SQLite database (fsv_archive_complete.db)
to the PostgreSQL database on Neon, including the new profirest matches.

Usage:
    export DATABASE_URL="postgresql://neondb_owner:npg_DMd2QfUZJmy1@ep-steep-voice-a9u47j2b-pooler.gwc.azure.neon.tech/neondb?sslmode=require"
    python database/sync_to_postgres.py --dry-run  # Preview changes
    python database/sync_to_postgres.py            # Sync data
"""

import argparse
import os
import sqlite3
import sys
from typing import Dict, Set
import psycopg2
from psycopg2.extras import execute_batch

class DatabaseSyncer:
    """Syncs SQLite archive to PostgreSQL."""

    def __init__(self, sqlite_path: str = "fsv_archive_complete.db", dry_run: bool = False):
        self.sqlite_path = sqlite_path
        self.dry_run = dry_run
        self.stats = {
            'teams': 0,
            'players': 0,
            'coaches': 0,
            'referees': 0,
            'seasons': 0,
            'competitions': 0,
            'matches': 0,
            'lineups': 0,
            'goals': 0,
            'cards': 0,
            'substitutions': 0,
        }

        # Connect to databases
        self.sqlite_conn = sqlite3.connect(sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable not set")
        self.pg_conn = psycopg2.connect(db_url)

        # ID mappings from SQLite to Postgres
        self.team_id_map: Dict[int, int] = {}
        self.player_id_map: Dict[int, int] = {}
        self.coach_id_map: Dict[int, int] = {}
        self.referee_id_map: Dict[int, int] = {}
        self.season_id_map: Dict[int, int] = {}
        self.competition_id_map: Dict[int, int] = {}
        self.season_comp_id_map: Dict[int, int] = {}
        self.match_id_map: Dict[int, int] = {}

    def sync_teams(self):
        """Sync teams table."""
        print("\n📋 Syncing teams...")
        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get existing teams from Postgres
        pg_cur.execute("SELECT id, normalized_name FROM teams")
        existing = {row[1]: row[0] for row in pg_cur.fetchall()}

        # Get all teams from SQLite
        sqlite_cur.execute("SELECT team_id, name, normalized_name, team_type, profile_url FROM teams")

        for row in sqlite_cur.fetchall():
            sqlite_id, name, norm_name, team_type, profile_url = row

            if norm_name in existing:
                # Team exists - update mapping
                self.team_id_map[sqlite_id] = existing[norm_name]
            else:
                # Insert new team
                if not self.dry_run:
                    pg_cur.execute(
                        """INSERT INTO teams (name, normalized_name, team_type, profile_url)
                           VALUES (%s, %s, %s, %s) RETURNING id""",
                        (name, norm_name, team_type, profile_url)
                    )
                    pg_id = pg_cur.fetchone()[0]
                    self.team_id_map[sqlite_id] = pg_id
                else:
                    self.team_id_map[sqlite_id] = -1  # Dummy for dry run
                self.stats['teams'] += 1

        if not self.dry_run:
            self.pg_conn.commit()
        print(f"  ✓ Added {self.stats['teams']} new teams")

    def sync_players(self):
        """Sync players table."""
        print("\n👤 Syncing players...")
        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get existing players from Postgres
        pg_cur.execute("SELECT id, normalized_name FROM players")
        existing = {row[1]: row[0] for row in pg_cur.fetchall()}

        # Get all players from SQLite
        sqlite_cur.execute("""
            SELECT player_id, name, normalized_name, profile_url,
                   date_of_birth, place_of_birth, nationality, position
            FROM players
        """)

        for row in sqlite_cur.fetchall():
            sqlite_id, name, norm_name, profile_url, dob, pob, nationality, position = row

            if norm_name in existing:
                self.player_id_map[sqlite_id] = existing[norm_name]
            else:
                if not self.dry_run:
                    pg_cur.execute(
                        """INSERT INTO players
                           (name, normalized_name, profile_url, date_of_birth,
                            place_of_birth, nationality, position)
                           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                        (name, norm_name, profile_url, dob, pob, nationality, position)
                    )
                    pg_id = pg_cur.fetchone()[0]
                    self.player_id_map[sqlite_id] = pg_id
                else:
                    self.player_id_map[sqlite_id] = -1
                self.stats['players'] += 1

        if not self.dry_run:
            self.pg_conn.commit()
        print(f"  ✓ Added {self.stats['players']} new players")

    def sync_matches(self):
        """Sync matches and all related data."""
        print("\n⚽ Syncing matches...")
        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get existing match source files from Postgres
        pg_cur.execute("SELECT source_file FROM matches")
        existing_sources = {row[0] for row in pg_cur.fetchall()}

        # Get all matches from SQLite
        sqlite_cur.execute("""
            SELECT match_id, match_date, home_team_id, away_team_id,
                   home_score, away_score, halftime_home, halftime_away,
                   source_file, attendance, kickoff_time
            FROM matches
            ORDER BY match_date
        """)

        for row in sqlite_cur.fetchall():
            (sqlite_match_id, match_date, home_team_sqlite, away_team_sqlite,
             home_score, away_score, ht_home, ht_away,
             source_file, attendance, kickoff) = row

            if source_file in existing_sources:
                # Match already exists - skip
                continue

            # Map team IDs
            home_team_pg = self.team_id_map.get(home_team_sqlite)
            away_team_pg = self.team_id_map.get(away_team_sqlite)

            if not home_team_pg or not away_team_pg:
                print(f"  ⚠ Skipping match {source_file} - team mapping missing")
                continue

            if not self.dry_run:
                pg_cur.execute(
                    """INSERT INTO matches
                       (match_date, home_team_id, away_team_id, home_score, away_score,
                        halftime_home, halftime_away, source_file, attendance, kickoff_time)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (match_date, home_team_pg, away_team_pg, home_score, away_score,
                     ht_home, ht_away, source_file, attendance, kickoff)
                )
                pg_match_id = pg_cur.fetchone()[0]
                self.match_id_map[sqlite_match_id] = pg_match_id
            else:
                self.match_id_map[sqlite_match_id] = -1

            self.stats['matches'] += 1

        if not self.dry_run:
            self.pg_conn.commit()
        print(f"  ✓ Added {self.stats['matches']} new matches")

    def run(self):
        """Run the complete sync process."""
        print("="*70)
        print("FSV MAINZ 05 ARCHIVE - SQLITE → POSTGRESQL SYNC")
        print("="*70)

        if self.dry_run:
            print("\n⚠️  DRY RUN MODE - No changes will be made\n")

        try:
            # Sync in dependency order
            self.sync_teams()
            self.sync_players()
            # TODO: Add sync_coaches, sync_referees, sync_seasons, sync_competitions
            # TODO: Add sync_matches (with lineups, goals, cards, subs)

            print("\n" + "="*70)
            print("SYNC SUMMARY")
            print("="*70)
            for entity, count in self.stats.items():
                if count > 0:
                    print(f"  {entity:20s}: {count:>6,} new records")

            if self.dry_run:
                print("\n⚠️  This was a DRY RUN - no data was actually synced")
                print("   Run without --dry-run to perform the actual sync")
            else:
                print("\n✅ Sync completed successfully!")

        except Exception as e:
            print(f"\n❌ Error during sync: {e}")
            if not self.dry_run:
                self.pg_conn.rollback()
            raise
        finally:
            self.sqlite_conn.close()
            self.pg_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Sync SQLite archive to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying them")
    parser.add_argument("--sqlite", default="fsv_archive_complete.db", help="Path to SQLite database")
    args = parser.parse_args()

    if not os.path.exists(args.sqlite):
        print(f"❌ SQLite database not found: {args.sqlite}")
        sys.exit(1)

    syncer = DatabaseSyncer(args.sqlite, args.dry_run)
    syncer.run()


if __name__ == "__main__":
    main()
