#!/usr/bin/env python3
"""
Sync profirest matches from SQLite to PostgreSQL with team ID mapping.

This script:
1. Creates a team ID mapping based on normalized_name (unique in both DBs)
2. Exports profirest matches from SQLite with mapped team IDs
3. Syncs matches with all related data (lineups, goals, cards, subs)

Usage:
    export DATABASE_URL="postgresql://..."
    python database/sync_profirest_matches.py --dry-run
    python database/sync_profirest_matches.py
"""

import argparse
import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
from typing import Dict, Optional

class ProfirestSyncer:
    """Sync profirest matches from SQLite to PostgreSQL"""

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

        # Build team ID mapping
        self.team_id_map: Dict[int, int] = {}  # sqlite_team_id -> pg_team_id
        self.player_id_map: Dict[int, int] = {}  # sqlite_player_id -> pg_player_id

    def build_team_mapping(self):
        """Build team ID mapping based on normalized_name"""
        print("🗺️  Building team ID mapping...")

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get all teams from both databases
        sqlite_cur.execute("SELECT team_id, normalized_name FROM teams")
        sqlite_teams = {row['normalized_name']: row['team_id'] for row in sqlite_cur.fetchall()}

        pg_cur.execute("SELECT team_id, normalized_name FROM teams")
        pg_teams = {row[1]: row[0] for row in pg_cur.fetchall()}

        # Build mapping
        for norm_name, sqlite_id in sqlite_teams.items():
            if norm_name in pg_teams:
                pg_id = pg_teams[norm_name]
                self.team_id_map[sqlite_id] = pg_id

        print(f"   ✓ Mapped {len(self.team_id_map)} teams")

        # Check for unmapped teams in profirest matches
        sqlite_cur.execute("""
            SELECT DISTINCT t.team_id, t.name, t.normalized_name
            FROM matches m
            JOIN teams t ON m.home_team_id = t.team_id OR m.away_team_id = t.team_id
            WHERE m.source_file LIKE '%profirest%'
            AND t.team_id NOT IN ({})
        """.format(','.join(str(tid) for tid in self.team_id_map.keys()) or '0'))

        unmapped = sqlite_cur.fetchall()
        if unmapped:
            print(f"   ⚠️  {len(unmapped)} teams in profirest matches not mapped:")
            for row in unmapped[:5]:
                print(f"      - {row['name']} (normalized: {row['normalized_name']})")
            if len(unmapped) > 5:
                print(f"      ... and {len(unmapped) - 5} more")

    def build_player_mapping(self):
        """Build player ID mapping based on normalized_name"""
        print("👤 Building player ID mapping...")

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get all players from both databases
        sqlite_cur.execute("SELECT player_id, normalized_name FROM players")
        sqlite_players = {row['normalized_name']: row['player_id'] for row in sqlite_cur.fetchall()}

        pg_cur.execute("SELECT player_id, normalized_name FROM players")
        pg_players = {row[1]: row[0] for row in pg_cur.fetchall()}

        # Build mapping
        for norm_name, sqlite_id in sqlite_players.items():
            if norm_name in pg_players:
                pg_id = pg_players[norm_name]
                self.player_id_map[sqlite_id] = pg_id

        print(f"   ✓ Mapped {len(self.player_id_map)} players")

    def sync_missing_teams(self):
        """Sync teams that exist in SQLite but not in PostgreSQL"""
        print("📋 Syncing missing teams...")

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get existing teams in PostgreSQL
        pg_cur.execute("SELECT normalized_name FROM teams")
        existing_pg_teams = {row[0] for row in pg_cur.fetchall()}

        # Get teams from profirest matches that aren't in PostgreSQL
        sqlite_cur.execute("""
            SELECT DISTINCT t.name, t.normalized_name, t.team_type, t.profile_url
            FROM matches m
            JOIN teams t ON m.home_team_id = t.team_id OR m.away_team_id = t.team_id
            WHERE m.source_file LIKE '%profirest%'
            AND t.normalized_name NOT IN ({})
        """.format(','.join(f"'{name}'" for name in existing_pg_teams) if existing_pg_teams else "''"))

        new_teams = []
        for row in sqlite_cur.fetchall():
            new_teams.append((row['name'], row['normalized_name'], row['team_type'], row['profile_url']))

        if new_teams and not self.dry_run:
            execute_batch(pg_cur, """
                INSERT INTO teams (name, normalized_name, team_type, profile_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (normalized_name) DO NOTHING
            """, new_teams, page_size=100)
            self.pg_conn.commit()

        self.stats['new_teams'] = len(new_teams)
        print(f"   ✓ {len(new_teams)} new teams {'would be' if self.dry_run else ''} added")

        # Rebuild team mapping after adding new teams
        if new_teams and not self.dry_run:
            self.build_team_mapping()

    def sync_profirest_matches(self):
        """Sync missing profirest matches"""
        print("⚽ Syncing profirest matches...")

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        # Get existing match source_files in PostgreSQL
        pg_cur.execute("SELECT source_file FROM matches WHERE source_file IS NOT NULL")
        existing_pg_matches = {row[0] for row in pg_cur.fetchall()}

        # Get profirest matches from SQLite that aren't in PostgreSQL
        sqlite_cur.execute("""
            SELECT match_id, season_competition_id, round_name, matchday, leg,
                   match_date, kickoff_time, venue, attendance, referee_id,
                   home_team_id, away_team_id, home_score, away_score,
                   halftime_home, halftime_away, extra_time_home, extra_time_away,
                   penalties_home, penalties_away, source_file
            FROM matches
            WHERE source_file LIKE '%profirest%'
            AND source_file NOT IN ({})
        """.format(','.join(f"'{sf}'" for sf in existing_pg_matches) if existing_pg_matches else "''"))

        new_matches = []
        skipped = 0
        sqlite_to_pg_match_ids = {}  # sqlite_match_id -> pg_match_id

        for row in sqlite_cur.fetchall():
            sqlite_match_id = row['match_id']
            home_team_id = row['home_team_id']
            away_team_id = row['away_team_id']

            # Map team IDs
            pg_home_id = self.team_id_map.get(home_team_id)
            pg_away_id = self.team_id_map.get(away_team_id)

            if not pg_home_id or not pg_away_id:
                skipped += 1
                continue

            new_matches.append((
                row['season_competition_id'], row['round_name'], row['matchday'], row['leg'],
                row['match_date'], row['kickoff_time'], row['venue'], row['attendance'], row['referee_id'],
                pg_home_id, pg_away_id, row['home_score'], row['away_score'],
                row['halftime_home'], row['halftime_away'], row['extra_time_home'], row['extra_time_away'],
                row['penalties_home'], row['penalties_away'], row['source_file'],
                sqlite_match_id  # Keep for later mapping
            ))

        synced_count = 0
        if new_matches and not self.dry_run:
            # Insert matches and get their new IDs
            for match_data in new_matches:
                sqlite_match_id = match_data[-1]
                pg_cur.execute("""
                    INSERT INTO matches (
                        season_competition_id, round_name, matchday, leg,
                        match_date, kickoff_time, venue, attendance, referee_id,
                        home_team_id, away_team_id, home_score, away_score,
                        halftime_home, halftime_away, extra_time_home, extra_time_away,
                        penalties_home, penalties_away, source_file
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING match_id
                """, match_data[:-1])  # Exclude sqlite_match_id

                pg_match_id = pg_cur.fetchone()[0]
                sqlite_to_pg_match_ids[sqlite_match_id] = pg_match_id
                synced_count += 1

            self.pg_conn.commit()

        self.stats['new_matches'] = len(new_matches)
        self.stats['skipped_matches'] = skipped
        self.sqlite_to_pg_match_ids = sqlite_to_pg_match_ids

        print(f"   ✓ {len(new_matches)} matches {'would be' if self.dry_run else ''} synced")
        if skipped > 0:
            print(f"   ⚠️  {skipped} matches skipped (unmapped teams)")

    def sync_match_lineups(self):
        """Sync lineups for newly added matches"""
        print("📋 Syncing match lineups...")

        if self.dry_run or not hasattr(self, 'sqlite_to_pg_match_ids'):
            print("   ✓ Skipped (dry run or no matches synced)")
            return

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        lineup_count = 0
        for sqlite_match_id, pg_match_id in self.sqlite_to_pg_match_ids.items():
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
        """Sync goals for newly added matches"""
        print("⚽ Syncing goals...")

        if self.dry_run or not hasattr(self, 'sqlite_to_pg_match_ids'):
            print("   ✓ Skipped (dry run or no matches synced)")
            return

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        goal_count = 0
        for sqlite_match_id, pg_match_id in self.sqlite_to_pg_match_ids.items():
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

                if pg_team_id:  # team_id is required
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
        """Sync cards for newly added matches"""
        print("🟨 Syncing cards...")

        if self.dry_run or not hasattr(self, 'sqlite_to_pg_match_ids'):
            print("   ✓ Skipped (dry run or no matches synced)")
            return

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        card_count = 0
        for sqlite_match_id, pg_match_id in self.sqlite_to_pg_match_ids.items():
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

                if pg_team_id:  # team_id is required
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
        """Sync substitutions for newly added matches"""
        print("🔄 Syncing substitutions...")

        if self.dry_run or not hasattr(self, 'sqlite_to_pg_match_ids'):
            print("   ✓ Skipped (dry run or no matches synced)")
            return

        sqlite_cur = self.sqlite_conn.cursor()
        pg_cur = self.pg_conn.cursor()

        sub_count = 0
        for sqlite_match_id, pg_match_id in self.sqlite_to_pg_match_ids.items():
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
        """Run complete sync"""
        print("=" * 70)
        print("PROFIREST MATCHES SYNC - SQLite → PostgreSQL")
        print("=" * 70)
        print()

        if self.dry_run:
            print("⚠️  DRY RUN MODE - No changes will be made\n")

        try:
            self.build_team_mapping()
            self.build_player_mapping()
            self.sync_missing_teams()
            self.sync_profirest_matches()
            self.sync_match_lineups()
            self.sync_goals()
            self.sync_cards()
            self.sync_substitutions()

            if not self.dry_run:
                self.pg_conn.commit()
                print("\n✅ Sync committed successfully!")
            else:
                self.pg_conn.rollback()
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
    parser = argparse.ArgumentParser(description="Sync profirest matches to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Preview without syncing")
    args = parser.parse_args()

    syncer = ProfirestSyncer(dry_run=args.dry_run)
    syncer.run()

if __name__ == "__main__":
    main()
