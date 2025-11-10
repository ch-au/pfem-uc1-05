#!/usr/bin/env python3
"""
Sync lineups, goals, cards, and substitutions for profirest matches already in PostgreSQL.

This script syncs all related data for profirest matches that were synced but are missing
their lineups, goals, cards, and substitutions.

Usage:
    export DATABASE_URL="postgresql://..."
    python database/sync_profirest_related_data.py --dry-run
    python database/sync_profirest_related_data.py
"""

import argparse
import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
from typing import Dict

class RelatedDataSyncer:
    """Sync related data for existing profirest matches"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.stats = {}

        # Connect to databases
        self.sqlite_conn = sqlite3.connect("fsv_archive_complete.db")
        self.sqlite_conn.row_factory = sqlite3.Row

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable not set")

        self.pg_conn = psycopg2.connect(db_url)
        self.pg_conn.autocommit = False

        # Build ID mappings
        self.team_id_map: Dict[int, int] = {}
        self.player_id_map: Dict[int, int] = {}
        self.match_id_map: Dict[int, int] = {}

    def build_mappings(self):
        """Build ID mappings between SQLite and PostgreSQL"""
        print("🗺️  Building ID mappings...")

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Team mapping
        sqlite_cur.execute("SELECT team_id, normalized_name FROM teams")
        sqlite_teams = {row['normalized_name']: row['team_id'] for row in sqlite_cur.fetchall()}

        pg_cur.execute("SELECT team_id, normalized_name FROM teams")
        pg_teams = {row[1]: row[0] for row in pg_cur.fetchall()}

        for norm_name, sqlite_id in sqlite_teams.items():
            if norm_name in pg_teams:
                self.team_id_map[sqlite_id] = pg_teams[norm_name]

        # Player mapping
        sqlite_cur.execute("SELECT player_id, normalized_name FROM players")
        sqlite_players = {row['normalized_name']: row['player_id'] for row in sqlite_cur.fetchall()}

        pg_cur.execute("SELECT player_id, normalized_name FROM players")
        pg_players = {row[1]: row[0] for row in pg_cur.fetchall()}

        for norm_name, sqlite_id in sqlite_players.items():
            if norm_name in pg_players:
                self.player_id_map[sqlite_id] = pg_players[norm_name]

        # Match mapping for profirest matches (based on source_file)
        sqlite_cur.execute("""
            SELECT match_id, source_file
            FROM matches
            WHERE source_file LIKE '%profirest%'
        """)
        sqlite_matches = {row['source_file']: row['match_id'] for row in sqlite_cur.fetchall()}

        pg_cur.execute("""
            SELECT match_id, source_file
            FROM matches
            WHERE source_file LIKE '%profirest%'
        """)
        pg_matches = {row[1]: row[0] for row in pg_cur.fetchall()}

        for source_file, sqlite_id in sqlite_matches.items():
            if source_file in pg_matches:
                self.match_id_map[sqlite_id] = pg_matches[source_file]

        print(f"   ✓ Mapped {len(self.team_id_map)} teams")
        print(f"   ✓ Mapped {len(self.player_id_map)} players")
        print(f"   ✓ Mapped {len(self.match_id_map)} profirest matches")

    def sync_lineups(self):
        """Sync lineups for profirest matches"""
        print("📋 Syncing match lineups...")

        if self.dry_run:
            print("   ✓ Skipped (dry run)")
            self.stats['lineups'] = 0
            return

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get profirest matches that don't have lineups yet
        pg_cur.execute("""
            SELECT m.match_id
            FROM matches m
            WHERE m.source_file LIKE '%profirest%'
            AND NOT EXISTS (
                SELECT 1 FROM match_lineups ml WHERE ml.match_id = m.match_id
            )
        """)
        matches_without_lineups = {row[0] for row in pg_cur.fetchall()}

        lineup_count = 0
        for sqlite_match_id, pg_match_id in self.match_id_map.items():
            if pg_match_id not in matches_without_lineups:
                continue

            # Get lineups from SQLite
            sqlite_cur.execute("""
                SELECT player_id, team_id, is_starter, shirt_number,
                       minute_on, stoppage_on, minute_off, stoppage_off
                FROM match_lineups
                WHERE match_id = ?
            """, (sqlite_match_id,))

            lineups = []
            for row in sqlite_cur.fetchall():
                pg_player_id = self.player_id_map.get(row['player_id'])
                pg_team_id = self.team_id_map.get(row['team_id'])
                if pg_player_id and pg_team_id:
                    lineups.append((
                        pg_match_id, pg_team_id, pg_player_id, row['shirt_number'],
                        bool(row['is_starter']), row['minute_on'], row['stoppage_on'],
                        row['minute_off'], row['stoppage_off']
                    ))

            if lineups:
                execute_batch(pg_cur, """
                    INSERT INTO match_lineups (
                        match_id, team_id, player_id, shirt_number, is_starter,
                        minute_on, stoppage_on, minute_off, stoppage_off
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, lineups, page_size=100)
                lineup_count += len(lineups)

        self.pg_conn.commit()
        self.stats['lineups'] = lineup_count
        print(f"   ✓ {lineup_count} lineups synced")

    def sync_goals(self):
        """Sync goals for profirest matches"""
        print("⚽ Syncing goals...")

        if self.dry_run:
            print("   ✓ Skipped (dry run)")
            self.stats['goals'] = 0
            return

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get profirest matches that don't have goals yet
        pg_cur.execute("""
            SELECT m.match_id
            FROM matches m
            WHERE m.source_file LIKE '%profirest%'
            AND NOT EXISTS (
                SELECT 1 FROM goals g WHERE g.match_id = m.match_id
            )
        """)
        matches_without_goals = {row[0] for row in pg_cur.fetchall()}

        goal_count = 0
        for sqlite_match_id, pg_match_id in self.match_id_map.items():
            if pg_match_id not in matches_without_goals:
                continue

            # Get goals from SQLite
            sqlite_cur.execute("""
                SELECT player_id, team_id, assist_player_id, minute, stoppage,
                       score_home, score_away, event_type
                FROM goals
                WHERE match_id = ?
            """, (sqlite_match_id,))

            goals = []
            for row in sqlite_cur.fetchall():
                pg_player_id = self.player_id_map.get(row['player_id']) if row['player_id'] else None
                pg_team_id = self.team_id_map.get(row['team_id']) if row['team_id'] else None
                pg_assist_id = self.player_id_map.get(row['assist_player_id']) if row['assist_player_id'] else None

                if pg_team_id:
                    goals.append((
                        pg_match_id, pg_team_id, pg_player_id, pg_assist_id, row['minute'],
                        row['stoppage'], row['score_home'], row['score_away'], row['event_type']
                    ))

            if goals:
                execute_batch(pg_cur, """
                    INSERT INTO goals (
                        match_id, team_id, player_id, assist_player_id, minute, stoppage,
                        score_home, score_away, event_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, goals, page_size=100)
                goal_count += len(goals)

        self.pg_conn.commit()
        self.stats['goals'] = goal_count
        print(f"   ✓ {goal_count} goals synced")

    def sync_cards(self):
        """Sync cards for profirest matches"""
        print("🟨 Syncing cards...")

        if self.dry_run:
            print("   ✓ Skipped (dry run)")
            self.stats['cards'] = 0
            return

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get profirest matches that don't have cards yet
        pg_cur.execute("""
            SELECT m.match_id
            FROM matches m
            WHERE m.source_file LIKE '%profirest%'
            AND NOT EXISTS (
                SELECT 1 FROM cards c WHERE c.match_id = m.match_id
            )
        """)
        matches_without_cards = {row[0] for row in pg_cur.fetchall()}

        card_count = 0
        for sqlite_match_id, pg_match_id in self.match_id_map.items():
            if pg_match_id not in matches_without_cards:
                continue

            # Get cards from SQLite
            sqlite_cur.execute("""
                SELECT player_id, team_id, minute, stoppage, card_type
                FROM cards
                WHERE match_id = ?
            """, (sqlite_match_id,))

            cards = []
            for row in sqlite_cur.fetchall():
                pg_player_id = self.player_id_map.get(row['player_id']) if row['player_id'] else None
                pg_team_id = self.team_id_map.get(row['team_id']) if row['team_id'] else None

                if pg_team_id:
                    cards.append((
                        pg_match_id, pg_team_id, pg_player_id, row['minute'],
                        row['stoppage'], row['card_type']
                    ))

            if cards:
                execute_batch(pg_cur, """
                    INSERT INTO cards (
                        match_id, team_id, player_id, minute, stoppage, card_type
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, cards, page_size=100)
                card_count += len(cards)

        self.pg_conn.commit()
        self.stats['cards'] = card_count
        print(f"   ✓ {card_count} cards synced")

    def sync_substitutions(self):
        """Sync substitutions for profirest matches"""
        print("🔄 Syncing substitutions...")

        if self.dry_run:
            print("   ✓ Skipped (dry run)")
            self.stats['substitutions'] = 0
            return

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get profirest matches that don't have substitutions yet
        pg_cur.execute("""
            SELECT m.match_id
            FROM matches m
            WHERE m.source_file LIKE '%profirest%'
            AND NOT EXISTS (
                SELECT 1 FROM match_substitutions ms WHERE ms.match_id = m.match_id
            )
        """)
        matches_without_subs = {row[0] for row in pg_cur.fetchall()}

        sub_count = 0
        for sqlite_match_id, pg_match_id in self.match_id_map.items():
            if pg_match_id not in matches_without_subs:
                continue

            # Get substitutions from SQLite
            sqlite_cur.execute("""
                SELECT player_on_id, player_off_id, team_id, minute, stoppage
                FROM match_substitutions
                WHERE match_id = ?
            """, (sqlite_match_id,))

            subs = []
            for row in sqlite_cur.fetchall():
                pg_player_on_id = self.player_id_map.get(row['player_on_id']) if row['player_on_id'] else None
                pg_player_off_id = self.player_id_map.get(row['player_off_id']) if row['player_off_id'] else None
                pg_team_id = self.team_id_map.get(row['team_id']) if row['team_id'] else None

                if pg_player_on_id and pg_player_off_id and pg_team_id:
                    subs.append((
                        pg_match_id, pg_team_id, row['minute'], row['stoppage'],
                        pg_player_on_id, pg_player_off_id
                    ))

            if subs:
                execute_batch(pg_cur, """
                    INSERT INTO match_substitutions (
                        match_id, team_id, minute, stoppage, player_on_id, player_off_id
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, subs, page_size=100)
                sub_count += len(subs)

        self.pg_conn.commit()
        self.stats['substitutions'] = sub_count
        print(f"   ✓ {sub_count} substitutions synced")

    def run(self):
        """Run complete sync of related data"""
        print("=" * 70)
        print("PROFIREST RELATED DATA SYNC - SQLite → PostgreSQL")
        print("=" * 70)
        print()

        if self.dry_run:
            print("⚠️  DRY RUN MODE - No changes will be made\n")

        try:
            self.build_mappings()
            self.sync_lineups()
            self.sync_goals()
            self.sync_cards()
            self.sync_substitutions()

            if not self.dry_run:
                print("\n✅ Sync committed successfully!")
            else:
                print("\n⚠️  DRY RUN - Rolling back (no changes made)")

            self.print_summary()

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self.pg_conn.rollback()
            raise
        finally:
            self.sqlite_conn.close()
            self.pg_conn.close()

    def print_summary(self):
        """Print sync summary"""
        print("\n" + "=" * 70)
        print("SYNC SUMMARY")
        print("=" * 70)
        for key, count in self.stats.items():
            print(f"  {key:25s}: {count:>6,}")

def main():
    parser = argparse.ArgumentParser(description="Sync related data for profirest matches")
    parser.add_argument("--dry-run", action="store_true", help="Preview without syncing")
    args = parser.parse_args()

    syncer = RelatedDataSyncer(dry_run=args.dry_run)
    syncer.run()

if __name__ == "__main__":
    main()
