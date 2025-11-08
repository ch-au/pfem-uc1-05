#!/usr/bin/env python3
"""
Complete Europapokal sync with match details and data quality fixes.

This script:
1. Syncs match details (lineups, goals, cards, substitutions) for Euro matches
2. Fixes competition classification (reclassify Bundesliga matches)
3. Validates data quality

Usage:
    python complete_euro_sync.py --dry-run
    python complete_euro_sync.py
"""

import argparse
import os
import sqlite3
import sys
from typing import Dict, List
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class CompleteEuroSyncer:
    """Complete sync and quality fix for Europapokal matches."""
    
    def __init__(self, sqlite_path: str, dry_run: bool = False):
        self.sqlite_path = sqlite_path
        self.dry_run = dry_run
        self.sqlite_conn = sqlite3.connect(sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row
        self.pg_conn = psycopg2.connect(os.getenv("DB_URL"))
        
        # ID mappings
        self.player_id_map: Dict[int, int] = {}
        self.team_id_map: Dict[int, int] = {}
        self.match_id_map: Dict[int, int] = {}
        
        # Statistics
        self.stats = {
            'goals_synced': 0,
            'lineups_synced': 0,
            'cards_synced': 0,
            'subs_synced': 0,
            'competitions_fixed': 0
        }
    
    def close(self):
        """Close connections."""
        self.sqlite_conn.close()
        self.pg_conn.close()
    
    def build_mappings(self):
        """Build ID mappings between SQLite and Postgres."""
        print("Building ID mappings...")
        
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
        
        # Map teams
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("SELECT team_id, name, normalized_name FROM public.teams")
            pg_teams_data = pg_cur.fetchall()
            pg_teams = {(row[1], row[2]): row[0] for row in pg_teams_data}
            pg_teams_by_norm = {row[2]: row[0] for row in pg_teams_data}
        
        sqlite_cur = self.sqlite_conn.execute("SELECT team_id, name, normalized_name FROM teams")
        for row in sqlite_cur.fetchall():
            # Exact match
            pg_id = pg_teams.get((row['name'], row['normalized_name']))
            if pg_id:
                self.team_id_map[row['team_id']] = pg_id
            # FSV special case
            elif row['name'] == 'FSV':
                for (pg_name, pg_norm), pg_id in pg_teams.items():
                    if 'fsv mainz' in pg_norm.lower():
                        self.team_id_map[row['team_id']] = pg_id
                        break
            # Normalized match
            elif row['normalized_name'] in pg_teams_by_norm:
                self.team_id_map[row['team_id']] = pg_teams_by_norm[row['normalized_name']]
        
        print(f"  Mapped {len(self.team_id_map)} teams")
        
        # Map the 6 Euro matches we just added (by date and teams)
        print("  Mapping Euro matches...")
        
        # Get Euro matches from SQLite
        sqlite_cur = self.sqlite_conn.execute("""
            SELECT m.match_id, m.match_date, t_home.name as home, t_away.name as away
            FROM matches m
            JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
            JOIN competitions c ON sc.competition_id = c.competition_id
            JOIN seasons s ON sc.season_id = s.season_id
            JOIN teams t_home ON m.home_team_id = t_home.team_id
            JOIN teams t_away ON m.away_team_id = t_away.team_id
            WHERE c.name = 'Europapokal' AND s.label = '2016-17'
            AND (t_home.name LIKE '%Saint%' OR t_away.name LIKE '%Saint%'
                 OR t_home.name LIKE '%Qəbələ%' OR t_away.name LIKE '%Qəbələ%'
                 OR t_home.name LIKE '%Anderlecht%' OR t_away.name LIKE '%Anderlecht%')
        """)
        
        sqlite_euro_matches = {
            f"{row['match_date']}|{row['home']}|{row['away']}": row['match_id']
            for row in sqlite_cur.fetchall()
        }
        
        # Get corresponding matches from Postgres (recently added)
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("""
                SELECT m.match_id, m.match_date::TEXT, t_home.name as home, t_away.name as away
                FROM public.matches m
                JOIN public.teams t_home ON m.home_team_id = t_home.team_id
                JOIN public.teams t_away ON m.away_team_id = t_away.team_id
                WHERE m.match_id >= 3354 AND m.match_id <= 3359
            """)
            
            for row in pg_cur.fetchall():
                pg_match_id, date, home, away = row
                # Try to match with SQLite (accounting for FSV name difference)
                for key, sqlite_id in sqlite_euro_matches.items():
                    key_date, key_home, key_away = key.split('|')
                    if key_date == date:
                        # Check if teams match (accounting for FSV vs "1. FSV Mainz 05")
                        home_match = (home == key_home or 
                                    (home == "FSV" and "FSV Mainz" in key_home) or
                                    (key_home == "FSV" and "FSV Mainz" in home))
                        away_match = (away == key_away or
                                    (away == "FSV" and "FSV Mainz" in key_away) or
                                    (key_away == "FSV" and "FSV Mainz" in away))
                        
                        if home_match and away_match:
                            self.match_id_map[sqlite_id] = pg_match_id
                            print(f"    Mapped match {sqlite_id} → {pg_match_id}: {date}")
                            break
        
        print(f"  Mapped {len(self.match_id_map)} Euro matches")
    
    def sync_match_details(self):
        """Sync lineups, goals, cards, and substitutions for Euro matches."""
        print(f"\nSyncing match details for {len(self.match_id_map)} Euro matches...")
        
        for sqlite_match_id, pg_match_id in self.match_id_map.items():
            print(f"\n  Match {pg_match_id} (SQLite ID: {sqlite_match_id}):")
            
            # Sync lineups
            self._sync_lineups(sqlite_match_id, pg_match_id)
            
            # Sync goals
            self._sync_goals(sqlite_match_id, pg_match_id)
            
            # Sync cards
            self._sync_cards(sqlite_match_id, pg_match_id)
            
            # Sync substitutions
            self._sync_substitutions(sqlite_match_id, pg_match_id)
    
    def _sync_lineups(self, sqlite_match_id: int, pg_match_id: int):
        """Sync match lineups."""
        sqlite_cur = self.sqlite_conn.execute("""
            SELECT * FROM match_lineups WHERE match_id = ?
        """, (sqlite_match_id,))
        
        lineups = sqlite_cur.fetchall()
        
        if self.dry_run:
            print(f"    [DRY RUN] Would sync {len(lineups)} lineups")
            return
        
        with self.pg_conn.cursor() as pg_cur:
            for lineup in lineups:
                pg_player_id = self.player_id_map.get(lineup['player_id'])
                pg_team_id = self.team_id_map.get(lineup['team_id'])
                
                if not pg_player_id or not pg_team_id:
                    continue
                
                pg_cur.execute("""
                    INSERT INTO public.match_lineups (
                        match_id, team_id, player_id, shirt_number, is_starter,
                        minute_on, stoppage_on, minute_off, stoppage_off
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    pg_match_id, pg_team_id, pg_player_id,
                    lineup['shirt_number'],
                    bool(lineup['is_starter']) if lineup['is_starter'] is not None else None,
                    lineup['minute_on'], lineup['stoppage_on'],
                    lineup['minute_off'], lineup['stoppage_off']
                ))
        
        self.pg_conn.commit()
        self.stats['lineups_synced'] += len(lineups)
        print(f"    ✓ Synced {len(lineups)} lineups")
    
    def _sync_goals(self, sqlite_match_id: int, pg_match_id: int):
        """Sync goals."""
        sqlite_cur = self.sqlite_conn.execute("""
            SELECT * FROM goals WHERE match_id = ?
        """, (sqlite_match_id,))
        
        goals = sqlite_cur.fetchall()
        
        if self.dry_run:
            print(f"    [DRY RUN] Would sync {len(goals)} goals")
            return
        
        with self.pg_conn.cursor() as pg_cur:
            for goal in goals:
                pg_player_id = self.player_id_map.get(goal['player_id'])
                pg_team_id = self.team_id_map.get(goal['team_id'])
                pg_assist_id = self.player_id_map.get(goal['assist_player_id']) if goal['assist_player_id'] else None
                
                if not pg_player_id or not pg_team_id:
                    continue
                
                pg_cur.execute("""
                    INSERT INTO public.goals (
                        match_id, team_id, player_id, assist_player_id,
                        minute, stoppage, score_home, score_away, event_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    pg_match_id, pg_team_id, pg_player_id, pg_assist_id,
                    goal['minute'], goal['stoppage'],
                    goal['score_home'], goal['score_away'], goal['event_type']
                ))
        
        self.pg_conn.commit()
        self.stats['goals_synced'] += len(goals)
        print(f"    ✓ Synced {len(goals)} goals")
    
    def _sync_cards(self, sqlite_match_id: int, pg_match_id: int):
        """Sync cards."""
        sqlite_cur = self.sqlite_conn.execute("""
            SELECT * FROM cards WHERE match_id = ?
        """, (sqlite_match_id,))
        
        cards = sqlite_cur.fetchall()
        
        if self.dry_run:
            print(f"    [DRY RUN] Would sync {len(cards)} cards")
            return
        
        with self.pg_conn.cursor() as pg_cur:
            for card in cards:
                pg_player_id = self.player_id_map.get(card['player_id'])
                pg_team_id = self.team_id_map.get(card['team_id'])
                
                if not pg_player_id or not pg_team_id:
                    continue
                
                pg_cur.execute("""
                    INSERT INTO public.cards (
                        match_id, team_id, player_id, minute, stoppage, card_type
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    pg_match_id, pg_team_id, pg_player_id,
                    card['minute'], card['stoppage'], card['card_type']
                ))
        
        self.pg_conn.commit()
        self.stats['cards_synced'] += len(cards)
        print(f"    ✓ Synced {len(cards)} cards")
    
    def _sync_substitutions(self, sqlite_match_id: int, pg_match_id: int):
        """Sync substitutions."""
        sqlite_cur = self.sqlite_conn.execute("""
            SELECT * FROM match_substitutions WHERE match_id = ?
        """, (sqlite_match_id,))
        
        subs = sqlite_cur.fetchall()
        
        if self.dry_run:
            print(f"    [DRY RUN] Would sync {len(subs)} substitutions")
            return
        
        with self.pg_conn.cursor() as pg_cur:
            for sub in subs:
                pg_player_on = self.player_id_map.get(sub['player_on_id'])
                pg_player_off = self.player_id_map.get(sub['player_off_id'])
                pg_team_id = self.team_id_map.get(sub['team_id'])
                
                if not pg_player_on or not pg_player_off or not pg_team_id:
                    continue
                
                pg_cur.execute("""
                    INSERT INTO public.match_substitutions (
                        match_id, team_id, minute, stoppage, player_on_id, player_off_id
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    pg_match_id, pg_team_id,
                    sub['minute'], sub['stoppage'],
                    pg_player_on, pg_player_off
                ))
        
        self.pg_conn.commit()
        self.stats['subs_synced'] += len(subs)
        print(f"    ✓ Synced {len(subs)} substitutions")
    
    def fix_competition_classification(self):
        """Fix Bundesliga matches incorrectly classified as Europapokal."""
        print("\nFixing competition classification...")
        
        # Get Bundesliga and Europapokal competition IDs
        with self.pg_conn.cursor() as pg_cur:
            pg_cur.execute("SELECT competition_id, name FROM public.competitions WHERE name IN ('Bundesliga', 'Europapokal')")
            comps = {row[1]: row[0] for row in pg_cur.fetchall()}
            
            bundesliga_id = comps.get('Bundesliga')
            europapokal_id = comps.get('Europapokal')
            
            if not bundesliga_id or not europapokal_id:
                print("  Error: Could not find competition IDs")
                return
            
            # Find 2016-17 season
            pg_cur.execute("SELECT season_id FROM public.seasons WHERE label = '2016-17'")
            season_result = pg_cur.fetchone()
            if not season_result:
                print("  Error: Could not find 2016-17 season")
                return
            
            season_id = season_result[0]
            
            # Get Bundesliga season_competition (should already exist)
            pg_cur.execute("""
                SELECT season_competition_id FROM public.season_competitions
                WHERE season_id = %s AND competition_id = %s
            """, (season_id, bundesliga_id))
            
            result = pg_cur.fetchone()
            if not result:
                print("  Error: Could not find Bundesliga season_competition for 2016-17")
                print("  This should exist. Please check the database.")
                return
            
            bundesliga_sc_id = result[0]
            
            # Get Europapokal season_competition
            pg_cur.execute("""
                SELECT season_competition_id FROM public.season_competitions
                WHERE season_id = %s AND competition_id = %s
            """, (season_id, europapokal_id))
            
            euro_result = pg_cur.fetchone()
            if not euro_result:
                print("  Error: Could not find Europapokal season_competition")
                return
            euro_sc_id = euro_result[0]
            
            # Find Bundesliga matches incorrectly classified as Europapokal
            # (those with round_name like "N. Spieltag")
            pg_cur.execute("""
                SELECT match_id, round_name, match_date, home_team_id, away_team_id
                FROM public.matches
                WHERE season_competition_id = %s
                AND round_name LIKE '%Spieltag%'
            """, (euro_sc_id,))
            
            bundesliga_matches = pg_cur.fetchall()
            
            print(f"  Found {len(bundesliga_matches)} Bundesliga matches misclassified as Europapokal")
            
            if self.dry_run:
                print(f"  [DRY RUN] Would reclassify {len(bundesliga_matches)} matches to Bundesliga")
                for match in bundesliga_matches[:5]:
                    print(f"    - Match {match[0]}: {match[1]} ({match[2]})")
                if len(bundesliga_matches) > 5:
                    print(f"    ... and {len(bundesliga_matches) - 5} more")
                return
            
            # Update matches to correct season_competition
            pg_cur.execute("""
                UPDATE public.matches
                SET season_competition_id = %s
                WHERE season_competition_id = %s
                AND round_name LIKE '%Spieltag%'
            """, (bundesliga_sc_id, euro_sc_id))
            
            self.pg_conn.commit()
            self.stats['competitions_fixed'] = len(bundesliga_matches)
            print(f"  ✓ Reclassified {len(bundesliga_matches)} matches to Bundesliga")
    
    def validate_data_quality(self):
        """Run quality checks on the synced data."""
        print("\nData Quality Validation:")
        print("=" * 80)
        
        with self.pg_conn.cursor() as pg_cur:
            # Check Europapokal matches
            pg_cur.execute("""
                SELECT COUNT(*) FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                WHERE c.name = 'Europapokal'
            """)
            euro_count = pg_cur.fetchone()[0]
            print(f"✓ Total Europapokal matches: {euro_count}")
            
            # Check match details for Euro matches
            pg_cur.execute("""
                SELECT 
                    COUNT(DISTINCT m.match_id) as matches,
                    COUNT(DISTINCT g.goal_id) as goals,
                    COUNT(DISTINCT ml.lineup_id) as lineups,
                    COUNT(DISTINCT c.card_id) as cards,
                    COUNT(DISTINCT ms.substitution_id) as subs
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.competitions comp ON sc.competition_id = comp.competition_id
                LEFT JOIN public.goals g ON m.match_id = g.match_id
                LEFT JOIN public.match_lineups ml ON m.match_id = ml.match_id
                LEFT JOIN public.cards c ON m.match_id = c.match_id
                LEFT JOIN public.match_substitutions ms ON m.match_id = ms.match_id
                WHERE comp.name = 'Europapokal'
                AND m.match_id >= 3354 AND m.match_id <= 3359
            """)
            
            result = pg_cur.fetchone()
            print(f"\n6 Recently Synced Euro Matches:")
            print(f"  - Matches: {result[0]}")
            print(f"  - Goals: {result[1]}")
            print(f"  - Lineups: {result[2]}")
            print(f"  - Cards: {result[3]}")
            print(f"  - Substitutions: {result[4]}")
            
            # Check 2016-17 Bundesliga matches
            pg_cur.execute("""
                SELECT COUNT(*) FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                WHERE c.name = 'Bundesliga' AND s.label = '2016-17'
            """)
            
            bundesliga_count = pg_cur.fetchone()[0]
            print(f"\n✓ 2016-17 Bundesliga matches: {bundesliga_count}")
    
    def run(self):
        """Run complete sync and quality fix process."""
        print("=" * 80)
        print("COMPLETE EUROPAPOKAL SYNC & QUALITY FIX")
        print("=" * 80)
        if self.dry_run:
            print("MODE: DRY RUN")
        else:
            print("MODE: LIVE")
        print()
        
        # Step 1: Build mappings
        self.build_mappings()
        
        # Step 2: Sync match details
        self.sync_match_details()
        
        # Step 3: Fix competition classification
        self.fix_competition_classification()
        
        # Step 4: Validate
        if not self.dry_run:
            self.validate_data_quality()
        
        # Summary
        print("\n" + "=" * 80)
        if self.dry_run:
            print("DRY RUN COMPLETE")
        else:
            print("✅ SYNC COMPLETE")
            print(f"\nStatistics:")
            print(f"  - Goals synced: {self.stats['goals_synced']}")
            print(f"  - Lineups synced: {self.stats['lineups_synced']}")
            print(f"  - Cards synced: {self.stats['cards_synced']}")
            print(f"  - Substitutions synced: {self.stats['subs_synced']}")
            print(f"  - Competitions fixed: {self.stats['competitions_fixed']}")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Complete Europapokal sync with quality fixes")
    parser.add_argument("--sqlite", default="fsv_archive_complete.db", help="SQLite database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()
    
    try:
        syncer = CompleteEuroSyncer(args.sqlite, dry_run=args.dry_run)
        syncer.run()
        syncer.close()
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

