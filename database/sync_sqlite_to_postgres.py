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
import sqlite3
import sys
from typing import Dict, List, Any
import psycopg2
from psycopg2.extras import execute_values

# Database paths
SQLITE_PATH = "fsv_archive_complete.db"
POSTGRES_URL = "postgresql://neondb_owner:npg_TUR24rnpzgGf@ep-muddy-scene-a9tpn6pu-pooler.gwc.azure.neon.tech/neondb?sslmode=require"


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
        sqlite_cur.execute(f"SELECT {', '.join(all_cols)} FROM {table_name}")
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
        insert_sql = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES %s
            RETURNING {id_column}
        """

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
            # 1. Teams (no FKs)
            self.sync_table(
                'teams',
                ['name', 'normalized_name', 'team_type', 'profile_url'],
                'team_id'
            )

            # 2. Competitions (no FKs)
            self.sync_table(
                'competitions',
                ['name', 'normalized_name', 'level', 'gender'],
                'competition_id'
            )

            # 3. Seasons (FK: team_id)
            self.sync_table(
                'seasons',
                ['label', 'start_year', 'end_year', 'team_id'],
                'season_id',
                fk_mappings={'team_id': 'teams'}
            )

            # 4. Season Competitions (FKs: season_id, competition_id)
            self.sync_table(
                'season_competitions',
                ['season_id', 'competition_id', 'stage_label', 'source_path'],
                'season_competition_id',
                fk_mappings={'season_id': 'seasons', 'competition_id': 'competitions'}
            )

            # 5. Referees (no FKs)
            self.sync_table(
                'referees',
                ['name', 'normalized_name', 'profile_url'],
                'referee_id'
            )

            # 6. Coaches (no FKs)
            self.sync_table(
                'coaches',
                ['name', 'normalized_name', 'birth_date', 'birth_place', 'nationality', 'profile_url'],
                'coach_id'
            )

            # 7. Players (no FKs)
            self.sync_table(
                'players',
                ['name', 'normalized_name', 'birth_date', 'birth_place', 'height_cm',
                 'weight_kg', 'primary_position', 'nationality', 'profile_url', 'image_url'],
                'player_id'
            )

            # 8. Player Aliases (FK: player_id)
            self.sync_table(
                'player_aliases',
                ['player_id', 'alias', 'normalized_alias'],
                'alias_id',
                fk_mappings={'player_id': 'players'}
            )

            # 9. Player Careers (FK: player_id)
            self.sync_table(
                'player_careers',
                ['player_id', 'team_name', 'start_year', 'end_year', 'notes'],
                'career_id',
                fk_mappings={'player_id': 'players'}
            )

            # 10. Coach Careers (FK: coach_id)
            self.sync_table(
                'coach_careers',
                ['coach_id', 'team_name', 'start_date', 'end_date', 'role'],
                'career_id',
                fk_mappings={'coach_id': 'coaches'}
            )

            # 11. Season Squads (FKs: season_competition_id, player_id)
            self.sync_table(
                'season_squads',
                ['season_competition_id', 'player_id', 'position_group', 'shirt_number', 'status', 'notes'],
                'season_squad_id',
                fk_mappings={'season_competition_id': 'season_competitions', 'player_id': 'players'}
            )

            # 12. Matches (FKs: season_competition_id, referee_id, home_team_id, away_team_id)
            self.sync_table(
                'matches',
                ['season_competition_id', 'round_name', 'matchday', 'leg', 'match_date',
                 'kickoff_time', 'venue', 'attendance', 'referee_id', 'home_team_id',
                 'away_team_id', 'home_score', 'away_score', 'halftime_home', 'halftime_away',
                 'extra_time_home', 'extra_time_away', 'penalties_home', 'penalties_away', 'source_file'],
                'match_id',
                fk_mappings={
                    'season_competition_id': 'season_competitions',
                    'referee_id': 'referees',
                    'home_team_id': 'teams',
                    'away_team_id': 'teams'
                }
            )

            # 13. Match Coaches (FKs: match_id, team_id, coach_id)
            self.sync_table(
                'match_coaches',
                ['match_id', 'team_id', 'coach_id', 'role'],
                'match_coach_id',
                fk_mappings={'match_id': 'matches', 'team_id': 'teams', 'coach_id': 'coaches'}
            )

            # 14. Match Referees (FKs: match_id, referee_id)
            self.sync_table(
                'match_referees',
                ['match_id', 'referee_id', 'role'],
                'match_referee_id',
                fk_mappings={'match_id': 'matches', 'referee_id': 'referees'}
            )

            # 15. Match Lineups (FKs: match_id, team_id, player_id)
            self.sync_table(
                'match_lineups',
                ['match_id', 'team_id', 'player_id', 'shirt_number', 'is_starter',
                 'minute_on', 'stoppage_on', 'minute_off', 'stoppage_off'],
                'lineup_id',
                fk_mappings={'match_id': 'matches', 'team_id': 'teams', 'player_id': 'players'}
            )

            # 16. Match Substitutions (FKs: match_id, team_id, player_on_id, player_off_id)
            self.sync_table(
                'match_substitutions',
                ['match_id', 'team_id', 'minute', 'stoppage', 'player_on_id', 'player_off_id'],
                'substitution_id',
                fk_mappings={
                    'match_id': 'matches',
                    'team_id': 'teams',
                    'player_on_id': 'players',
                    'player_off_id': 'players'
                }
            )

            # 17. Goals (FKs: match_id, team_id, player_id, assist_player_id)
            self.sync_table(
                'goals',
                ['match_id', 'team_id', 'player_id', 'assist_player_id', 'minute',
                 'stoppage', 'score_home', 'score_away', 'event_type'],
                'goal_id',
                fk_mappings={
                    'match_id': 'matches',
                    'team_id': 'teams',
                    'player_id': 'players',
                    'assist_player_id': 'players'
                }
            )

            # 18. Cards (FKs: match_id, team_id, player_id)
            self.sync_table(
                'cards',
                ['match_id', 'team_id', 'player_id', 'minute', 'stoppage', 'card_type'],
                'card_id',
                fk_mappings={'match_id': 'matches', 'team_id': 'teams', 'player_id': 'players'}
            )

            # 19. Match Notes (FK: match_id)
            self.sync_table(
                'match_notes',
                ['match_id', 'note', 'note_type'],
                'note_id',
                fk_mappings={'match_id': 'matches'}
            )

            # 20. Season Matchdays (FK: season_competition_id)
            self.sync_table(
                'season_matchdays',
                ['season_competition_id', 'matchday', 'date', 'position', 'points',
                 'goals_for', 'goals_against', 'goal_difference'],
                'season_matchday_id',
                fk_mappings={'season_competition_id': 'season_competitions'}
            )

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


def main():
    parser = argparse.ArgumentParser(description="Sync SQLite to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Preview without syncing")
    parser.add_argument("--sqlite", default=SQLITE_PATH, help="SQLite database path")
    args = parser.parse_args()

    if not os.path.exists(args.sqlite):
        print(f"ERROR: SQLite database not found: {args.sqlite}")
        sys.exit(1)

    engine = SyncEngine(args.sqlite, POSTGRES_URL, dry_run=args.dry_run)

    try:
        engine.sync_all()
    finally:
        engine.close()


if __name__ == "__main__":
    main()
