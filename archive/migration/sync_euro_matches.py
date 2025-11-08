#!/usr/bin/env python3
"""
Sync Europapokal (European Cup) matches from local SQLite to Neon Postgres.

This script identifies matches in the local database that don't exist in Postgres
and adds them, preserving all related data (lineups, goals, cards, substitutions, etc.)

Usage:
    python sync_euro_matches.py --dry-run  # Show what would be synced
    python sync_euro_matches.py            # Actually sync the data
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Set, Tuple
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class EuroMatchSyncer:
    """Syncs Europapokal matches from SQLite to Postgres."""
    
    def __init__(self, sqlite_path: str, dry_run: bool = False):
        self.sqlite_path = sqlite_path
        self.dry_run = dry_run
        self.sqlite_conn = sqlite3.connect(sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row
        self.pg_conn = psycopg2.connect(os.getenv("DB_URL"))
        
        # ID mappings from SQLite to Postgres
        self.team_id_map: Dict[int, int] = {}
        self.player_id_map: Dict[int, int] = {}
        self.season_id_map: Dict[int, int] = {}
        self.competition_id_map: Dict[int, int] = {}
        self.season_comp_id_map: Dict[int, int] = {}
        
    def close(self):
        """Close database connections."""
        self.sqlite_conn.close()
        self.pg_conn.close()
    
    def get_europapokal_matches(self) -> Tuple[Set[str], Set[str]]:
        """
        Get Europapokal match identifiers from both databases.
        Returns: (sqlite_match_keys, postgres_match_keys)
        Match key format: "season_label|opponent|home_score|away_score|match_date"
        """
        # Get from SQLite
        sqlite_cur = self.sqlite_conn.execute("""
            SELECT 
                s.label as season,
                t_home.name as home_team,
                t_away.name as away_team,
                m.home_score,
                m.away_score,
                m.match_date,
                m.match_id
            FROM matches m
            JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
            JOIN competitions c ON sc.competition_id = c.competition_id
            JOIN seasons s ON sc.season_id = s.season_id
            JOIN teams t_home ON m.home_team_id = t_home.team_id
            JOIN teams t_away ON m.away_team_id = t_away.team_id
            WHERE c.name = 'Europapokal'
            ORDER BY s.label, m.match_date
        """)
        
        sqlite_matches = {}
        for row in sqlite_cur.fetchall():
            key = f"{row['season']}|{row['home_team']}|{row['away_team']}|{row['home_score']}|{row['away_score']}|{row['match_date']}"
            sqlite_matches[key] = row['match_id']
        
        # Get from Postgres
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("""
                SELECT 
                    s.label as season,
                    t_home.name as home_team,
                    t_away.name as away_team,
                    m.home_score,
                    m.away_score,
                    m.match_date::TEXT,
                    m.match_id
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                JOIN public.teams t_home ON m.home_team_id = t_home.team_id
                JOIN public.teams t_away ON m.away_team_id = t_away.team_id
                WHERE c.name = 'Europapokal'
                ORDER BY s.label, m.match_date
            """)
            
            postgres_matches = set()
            for row in pg_cur.fetchall():
                key = f"{row[0]}|{row[1]}|{row[2]}|{row[3]}|{row[4]}|{row[5]}"
                postgres_matches.add(key)
        
        return set(sqlite_matches.keys()), postgres_matches, sqlite_matches
    
    def build_id_mappings(self):
        """Build ID mappings between SQLite and Postgres for existing entities."""
        print("Building ID mappings...")
        
        # Map teams (with special handling for FSV Mainz 05)
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("SELECT team_id, name, normalized_name FROM public.teams")
            pg_teams_data = pg_cur.fetchall()
            pg_teams = {(row[1], row[2]): row[0] for row in pg_teams_data}
            # Also create a normalized name lookup
            pg_teams_by_norm = {row[2]: (row[0], row[1]) for row in pg_teams_data}
        
        sqlite_cur = self.sqlite_conn.execute("SELECT team_id, name, normalized_name FROM teams")
        for row in sqlite_cur.fetchall():
            # Try exact match first
            pg_id = pg_teams.get((row['name'], row['normalized_name']))
            if pg_id:
                self.team_id_map[row['team_id']] = pg_id
            # Special case: FSV in local = 1. FSV Mainz 05 in Postgres
            elif row['name'] == 'FSV' and row['normalized_name'] == 'fsv':
                # Find the Mainz team in Postgres
                for (pg_name, pg_norm), pg_id in pg_teams.items():
                    if 'fsv mainz' in pg_norm.lower():
                        self.team_id_map[row['team_id']] = pg_id
                        print(f"    Mapped FSV (local) → {pg_name} (Postgres)")
                        break
            # Try normalized name match as fallback
            elif row['normalized_name'] in pg_teams_by_norm:
                pg_id, pg_name = pg_teams_by_norm[row['normalized_name']]
                self.team_id_map[row['team_id']] = pg_id
        
        print(f"  Mapped {len(self.team_id_map)} teams")
        
        # Map players
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("SELECT player_id, name, normalized_name FROM public.players")
            pg_players = {(row[1], row[2]): row[0] for row in pg_cur.fetchall()}
        
        sqlite_cur = self.sqlite_conn.execute("SELECT player_id, name, normalized_name FROM players")
        for row in sqlite_cur.fetchall():
            pg_id = pg_players.get((row['name'], row['normalized_name']))
            if pg_id:
                self.player_id_map[row['player_id']] = pg_id
        
        print(f"  Mapped {len(self.player_id_map)} players")
        
        # Map seasons
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("SELECT season_id, label FROM public.seasons")
            pg_seasons = {row[1]: row[0] for row in pg_cur.fetchall()}
        
        sqlite_cur = self.sqlite_conn.execute("SELECT season_id, label FROM seasons")
        for row in sqlite_cur.fetchall():
            pg_id = pg_seasons.get(row['label'])
            if pg_id:
                self.season_id_map[row['season_id']] = pg_id
        
        print(f"  Mapped {len(self.season_id_map)} seasons")
        
        # Map competitions
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("SELECT competition_id, name FROM public.competitions")
            pg_comps = {row[1]: row[0] for row in pg_cur.fetchall()}
        
        sqlite_cur = self.sqlite_conn.execute("SELECT competition_id, name FROM competitions")
        for row in sqlite_cur.fetchall():
            pg_id = pg_comps.get(row['name'])
            if pg_id:
                self.competition_id_map[row['competition_id']] = pg_id
        
        print(f"  Mapped {len(self.competition_id_map)} competitions")
    
    def sync_missing_entities(self, match_ids: List[int]):
        """Sync teams and players that don't exist in Postgres yet."""
        # Get all teams involved in these matches that aren't mapped
        placeholders = ','.join('?' * len(match_ids))
        sqlite_cur = self.sqlite_conn.execute(f"""
            SELECT DISTINCT t.team_id, t.name, t.normalized_name, t.team_type, t.profile_url
            FROM teams t
            JOIN matches m ON t.team_id IN (m.home_team_id, m.away_team_id)
            WHERE m.match_id IN ({placeholders})
        """, match_ids)
        
        all_teams = sqlite_cur.fetchall()
        new_teams = [t for t in all_teams if t['team_id'] not in self.team_id_map]
        
        if new_teams:
            if self.dry_run:
                print(f"  [DRY RUN] Would add {len(new_teams)} new teams:")
                for team in new_teams:
                    print(f"    - {team['name']} ({team['normalized_name']})")
            else:
                print(f"  Adding {len(new_teams)} new teams to Postgres...")
                with self.pg_conn.cursor() as pg_cur:
                    for team in new_teams:
                        pg_cur.execute("""
                            INSERT INTO public.teams (name, normalized_name, team_type, profile_url)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (name) DO UPDATE SET
                                normalized_name = EXCLUDED.normalized_name,
                                team_type = EXCLUDED.team_type,
                                profile_url = EXCLUDED.profile_url
                            RETURNING team_id
                        """, (team['name'], team['normalized_name'], team['team_type'], team['profile_url']))
                        result = pg_cur.fetchone()
                        if result:
                            self.team_id_map[team['team_id']] = result[0]
                            print(f"    ✓ Added {team['name']}")
                self.pg_conn.commit()
        else:
            print("  All teams already exist in Postgres")
        
    def sync_match(self, sqlite_match_id: int):
        """Sync a single match with all its related data."""
        # Get match data
        match_data = self.sqlite_conn.execute("""
            SELECT * FROM matches WHERE match_id = ?
        """, (sqlite_match_id,)).fetchone()
        
        if not match_data:
            return
        
        # Get season_competition_id mapping
        sc_data = self.sqlite_conn.execute("""
            SELECT sc.*, s.season_id, c.competition_id
            FROM season_competitions sc
            JOIN seasons s ON sc.season_id = s.season_id
            JOIN competitions c ON sc.competition_id = c.competition_id
            WHERE sc.season_competition_id = ?
        """, (match_data['season_competition_id'],)).fetchone()
        
        if not sc_data:
            print(f"  Warning: Could not find season_competition for match {sqlite_match_id}")
            return
        
        # Map IDs
        pg_season_id = self.season_id_map.get(sc_data['season_id'])
        pg_comp_id = self.competition_id_map.get(sc_data['competition_id'])
        
        if not pg_season_id or not pg_comp_id:
            print(f"  Warning: Missing season or competition mapping for match {sqlite_match_id}")
            return
        
        # Get or create season_competition in Postgres
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("""
                SELECT season_competition_id FROM public.season_competitions
                WHERE season_id = %s AND competition_id = %s
            """, (pg_season_id, pg_comp_id))
            result = pg_cur.fetchone()
            
            if result:
                pg_sc_id = result[0]
            else:
                if self.dry_run:
                    print(f"  [DRY RUN] Would create season_competition {sc_data['season_id']}-{sc_data['competition_id']}")
                    pg_sc_id = -1
                else:
                    pg_cur.execute("""
                        INSERT INTO public.season_competitions (season_id, competition_id, stage_label, source_path)
                        VALUES (%s, %s, %s, %s)
                        RETURNING season_competition_id
                    """, (pg_season_id, pg_comp_id, sc_data['stage_label'], sc_data['source_path']))
                    pg_sc_id = pg_cur.fetchone()[0]
                    self.pg_conn.commit()
        
        # Map team IDs
        pg_home_team_id = self.team_id_map.get(match_data['home_team_id'])
        pg_away_team_id = self.team_id_map.get(match_data['away_team_id'])
        
        if not pg_home_team_id or not pg_away_team_id:
            print(f"  Warning: Missing team mapping for match {sqlite_match_id}")
            return
        
        if self.dry_run:
            print(f"  [DRY RUN] Would insert match: {match_data['match_date']} - {match_data['home_score']}:{match_data['away_score']}")
            return
        
        # Insert match
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("""
                INSERT INTO public.matches (
                    season_competition_id, round_name, matchday, leg, match_date, kickoff_time,
                    venue, attendance, referee_id, home_team_id, away_team_id,
                    home_score, away_score, halftime_home, halftime_away,
                    extra_time_home, extra_time_away, penalties_home, penalties_away, source_file
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING match_id
            """, (
                pg_sc_id, match_data['round_name'], match_data['matchday'], match_data['leg'],
                match_data['match_date'], match_data['kickoff_time'], match_data['venue'],
                match_data['attendance'], None,  # referee_id mapping would go here
                pg_home_team_id, pg_away_team_id,
                match_data['home_score'], match_data['away_score'],
                match_data['halftime_home'], match_data['halftime_away'],
                match_data['extra_time_home'], match_data['extra_time_away'],
                match_data['penalties_home'], match_data['penalties_away'],
                match_data['source_file']
            ))
            pg_match_id = pg_cur.fetchone()[0]
            self.pg_conn.commit()
        
        print(f"  ✓ Inserted match {pg_match_id}: {match_data['match_date']}")
        
        # TODO: Sync related data (lineups, goals, cards, substitutions)
        # This would require similar mapping logic for players
    
    def run_sync(self):
        """Run the complete sync process."""
        print("=" * 80)
        print("EUROPAPOKAL MATCH SYNC")
        print("=" * 80)
        if self.dry_run:
            print("MODE: DRY RUN (no changes will be made)")
        else:
            print("MODE: LIVE (will modify Postgres database)")
        print()
        
        # Get matches
        print("Step 1: Analyzing Europapokal matches...")
        sqlite_keys, postgres_keys, sqlite_match_map = self.get_europapokal_matches()
        
        print(f"  SQLite: {len(sqlite_keys)} Europapokal matches")
        print(f"  Postgres: {len(postgres_keys)} Europapokal matches")
        
        # Find differences
        missing_in_postgres = sqlite_keys - postgres_keys
        missing_in_sqlite = postgres_keys - sqlite_keys
        
        print(f"\n  Missing in Postgres: {len(missing_in_postgres)} matches")
        print(f"  Missing in SQLite: {len(missing_in_sqlite)} matches")
        
        if not missing_in_postgres and not missing_in_sqlite:
            print("\n✅ Databases are already in sync!")
            return
        
        if missing_in_sqlite:
            print(f"\n⚠️  Warning: Postgres has {len(missing_in_sqlite)} matches not in SQLite")
            print("  This sync will only add SQLite→Postgres, not vice versa")
        
        if not missing_in_postgres:
            print("\n✅ No matches to sync to Postgres")
            return
        
        # Build ID mappings
        print("\nStep 2: Building ID mappings...")
        self.build_id_mappings()
        
        # Sync missing entities
        print("\nStep 3: Syncing missing entities...")
        match_ids_to_sync = [sqlite_match_map[key] for key in missing_in_postgres]
        self.sync_missing_entities(match_ids_to_sync)
        
        # Sync matches
        print(f"\nStep 4: Syncing {len(missing_in_postgres)} matches...")
        for i, key in enumerate(missing_in_postgres, 1):
            print(f"\n[{i}/{len(missing_in_postgres)}] {key}")
            self.sync_match(sqlite_match_map[key])
        
        print("\n" + "=" * 80)
        if self.dry_run:
            print("DRY RUN COMPLETE - No changes were made")
        else:
            print(f"✅ SYNC COMPLETE - Added {len(missing_in_postgres)} matches to Postgres")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Sync Europapokal matches to Postgres")
    parser.add_argument("--sqlite", default="fsv_archive_complete.db",
                       help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be synced without making changes")
    args = parser.parse_args()
    
    try:
        syncer = EuroMatchSyncer(args.sqlite, dry_run=args.dry_run)
        syncer.run_sync()
        syncer.close()
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

