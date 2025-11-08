#!/usr/bin/env python3
"""
Fix the mapping issue for Euro matches - sync ALL players and goals, not just FSV.

This script:
1. Maps ALL players involved in Euro matches (not just those already in Postgres)
2. Adds missing opponent players to Postgres
3. Re-syncs goals and lineups with complete mappings
"""

import os
import sqlite3
import sys
from typing import Dict, Set
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_euro_match_ids(sqlite_conn):
    """Get the 6 Euro match IDs from SQLite."""
    cur = sqlite_conn.execute("""
        SELECT m.match_id
        FROM matches m
        JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
        JOIN competitions c ON sc.competition_id = c.competition_id
        JOIN seasons s ON sc.season_id = s.season_id
        WHERE c.name = 'Europapokal' AND s.label = '2016-17'
        AND m.match_id IN (3018, 3019, 3020, 3021, 3022, 3023)
    """)
    return [row[0] for row in cur.fetchall()]


def build_player_mappings(sqlite_conn, pg_conn, match_ids):
    """Build complete player mappings including opponent players."""
    print("Building complete player mappings...")
    
    # Get all players in Postgres
    with pg_conn.cursor() as pg_cur:
        pg_cur.execute("SELECT player_id, name, normalized_name FROM public.players")
        pg_players = {(row[1], row[2]): row[0] for row in pg_cur.fetchall()}
        pg_players_by_name = {row[1]: row[0] for row in pg_cur.fetchall()}
    
    print(f"  Postgres has {len(pg_players)} players")
    
    # Get all players involved in these Euro matches (from all tables)
    placeholders = ','.join('?' * len(match_ids))
    
    # From lineups
    cur = sqlite_conn.execute(f"""
        SELECT DISTINCT p.player_id, p.name, p.normalized_name
        FROM players p
        JOIN match_lineups ml ON p.player_id = ml.player_id
        WHERE ml.match_id IN ({placeholders})
    """, match_ids)
    
    lineup_players = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    print(f"  Found {len(lineup_players)} unique players in lineups")
    
    # From goals
    cur = sqlite_conn.execute(f"""
        SELECT DISTINCT p.player_id, p.name, p.normalized_name
        FROM players p
        JOIN goals g ON p.player_id = g.player_id
        WHERE g.match_id IN ({placeholders})
    """, match_ids)
    
    goal_players = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    print(f"  Found {len(goal_players)} unique players in goals")
    
    # Combine all players
    all_players = {**lineup_players, **goal_players}
    print(f"  Total unique players needed: {len(all_players)}")
    
    # Build mapping
    player_id_map = {}
    missing_players = []
    
    for sqlite_id, (name, norm_name) in all_players.items():
        # Try exact match
        pg_id = pg_players.get((name, norm_name))
        if pg_id:
            player_id_map[sqlite_id] = pg_id
        # Try name-only match
        elif name in pg_players_by_name:
            player_id_map[sqlite_id] = pg_players_by_name[name]
        else:
            missing_players.append((sqlite_id, name, norm_name))
    
    print(f"  Mapped {len(player_id_map)} players")
    print(f"  Missing {len(missing_players)} players")
    
    if missing_players:
        print(f"\n  Adding {len(missing_players)} missing players to Postgres...")
        with pg_conn.cursor() as pg_cur:
            for sqlite_id, name, norm_name in missing_players:
                # Get player details from SQLite
                cur = sqlite_conn.execute("""
                    SELECT name, normalized_name, birth_date, birth_place, 
                           height_cm, weight_kg, primary_position, nationality, 
                           profile_url, image_url
                    FROM players WHERE player_id = ?
                """, (sqlite_id,))
                player_data = cur.fetchone()
                
                if player_data:
                    pg_cur.execute("""
                        INSERT INTO public.players (
                            name, normalized_name, birth_date, birth_place,
                            height_cm, weight_kg, primary_position, nationality,
                            profile_url, image_url
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (name) DO UPDATE SET
                            normalized_name = EXCLUDED.normalized_name,
                            birth_date = COALESCE(EXCLUDED.birth_date, public.players.birth_date),
                            primary_position = COALESCE(EXCLUDED.primary_position, public.players.primary_position)
                        RETURNING player_id
                    """, player_data)
                    
                    result = pg_cur.fetchone()
                    if result:
                        player_id_map[sqlite_id] = result[0]
                        print(f"    ✓ Added {name}")
        
        pg_conn.commit()
        print(f"  Now mapped {len(player_id_map)} total players")
    
    return player_id_map


def build_team_mappings(sqlite_conn, pg_conn, match_ids):
    """Build complete team mappings."""
    print("\nBuilding complete team mappings...")
    
    # Get all teams in Postgres
    with pg_conn.cursor() as pg_cur:
        pg_cur.execute("SELECT team_id, name, normalized_name FROM public.teams")
        pg_teams_data = pg_cur.fetchall()
        pg_teams = {(row[1], row[2]): row[0] for row in pg_teams_data}
        pg_teams_by_norm = {row[2]: row[0] for row in pg_teams_data}
    
    # Get all teams from Euro matches
    placeholders = ','.join('?' * len(match_ids))
    cur = sqlite_conn.execute(f"""
        SELECT DISTINCT t.team_id, t.name, t.normalized_name
        FROM teams t
        JOIN matches m ON t.team_id IN (m.home_team_id, m.away_team_id)
        WHERE m.match_id IN ({placeholders})
    """, match_ids)
    
    team_id_map = {}
    for row in cur.fetchall():
        sqlite_id, name, norm_name = row
        
        # Exact match
        pg_id = pg_teams.get((name, norm_name))
        if pg_id:
            team_id_map[sqlite_id] = pg_id
        # FSV special case
        elif name == 'FSV':
            for (pg_name, pg_norm), pg_id in pg_teams.items():
                if 'fsv mainz' in pg_norm.lower():
                    team_id_map[sqlite_id] = pg_id
                    print(f"  Mapped FSV → {pg_name}")
                    break
        # Normalized match
        elif norm_name in pg_teams_by_norm:
            team_id_map[sqlite_id] = pg_teams_by_norm[norm_name]
    
    print(f"  Mapped {len(team_id_map)} teams")
    return team_id_map


def get_postgres_match_mapping(sqlite_conn, pg_conn):
    """Map SQLite Euro match IDs to Postgres match IDs."""
    print("\nMapping Euro matches...")
    
    # Get SQLite matches
    sqlite_matches = {}
    cur = sqlite_conn.execute("""
        SELECT m.match_id, m.match_date, t_home.name, t_away.name
        FROM matches m
        JOIN teams t_home ON m.home_team_id = t_home.team_id
        JOIN teams t_away ON m.away_team_id = t_away.team_id
        WHERE m.match_id IN (3018, 3019, 3020, 3021, 3022, 3023)
    """)
    
    for row in cur.fetchall():
        key = f"{row[1]}|{row[2]}|{row[3]}"
        sqlite_matches[key] = row[0]
    
    # Get Postgres matches
    match_id_map = {}
    with pg_conn.cursor() as pg_cur:
        pg_cur.execute("""
            SELECT m.match_id, m.match_date::TEXT, t_home.name, t_away.name
            FROM public.matches m
            JOIN public.teams t_home ON m.home_team_id = t_home.team_id
            JOIN public.teams t_away ON m.away_team_id = t_away.team_id
            WHERE m.match_id >= 3354 AND m.match_id <= 3359
        """)
        
        for row in pg_cur.fetchall():
            pg_match_id, date, home, away = row
            # Try exact match
            key = f"{date}|{home}|{away}"
            if key in sqlite_matches:
                match_id_map[sqlite_matches[key]] = pg_match_id
                continue
            
            # Try with FSV variation
            for sqlite_key, sqlite_id in sqlite_matches.items():
                s_date, s_home, s_away = sqlite_key.split('|')
                if s_date == date:
                    home_match = (home == s_home or 
                                (s_home == "FSV" and "FSV Mainz" in home) or
                                (home == "FSV" and "FSV Mainz" in s_home))
                    away_match = (away == s_away or
                                (s_away == "FSV" and "FSV Mainz" in away) or
                                (away == "FSV" and "FSV Mainz" in s_away))
                    
                    if home_match and away_match:
                        match_id_map[sqlite_id] = pg_match_id
                        break
    
    print(f"  Mapped {len(match_id_map)} matches")
    return match_id_map


def resync_goals(sqlite_conn, pg_conn, match_id_map, player_id_map, team_id_map):
    """Re-sync ALL goals with proper mappings."""
    print("\nRe-syncing goals...")
    
    # First, delete existing goals for these matches to avoid duplicates
    with pg_conn.cursor() as pg_cur:
        pg_match_ids = list(match_id_map.values())
        placeholders = ','.join(['%s'] * len(pg_match_ids))
        pg_cur.execute(f"""
            DELETE FROM public.goals 
            WHERE match_id IN ({placeholders})
        """, pg_match_ids)
        deleted = pg_cur.rowcount
        print(f"  Deleted {deleted} existing goals")
    
    pg_conn.commit()
    
    # Sync all goals
    total_synced = 0
    for sqlite_match_id, pg_match_id in match_id_map.items():
        cur = sqlite_conn.execute("""
            SELECT * FROM goals WHERE match_id = ?
        """, (sqlite_match_id,))
        
        goals = cur.fetchall()
        synced = 0
        
        with pg_conn.cursor() as pg_cur:
            for goal in goals:
                pg_player_id = player_id_map.get(goal['player_id'])
                pg_team_id = team_id_map.get(goal['team_id'])
                pg_assist_id = player_id_map.get(goal['assist_player_id']) if goal['assist_player_id'] else None
                
                if not pg_player_id or not pg_team_id:
                    print(f"    Warning: Missing mapping for goal - player_id={goal['player_id']}, team_id={goal['team_id']}")
                    continue
                
                pg_cur.execute("""
                    INSERT INTO public.goals (
                        match_id, team_id, player_id, assist_player_id,
                        minute, stoppage, score_home, score_away, event_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    pg_match_id, pg_team_id, pg_player_id, pg_assist_id,
                    goal['minute'], goal['stoppage'],
                    goal['score_home'], goal['score_away'], goal['event_type']
                ))
                synced += 1
        
        pg_conn.commit()
        total_synced += synced
        if synced > 0:
            print(f"  Match {pg_match_id}: synced {synced} goals")
    
    print(f"  ✓ Total goals synced: {total_synced}")


def resync_lineups(sqlite_conn, pg_conn, match_id_map, player_id_map, team_id_map):
    """Re-sync ALL lineups with proper mappings."""
    print("\nRe-syncing lineups...")
    
    # Delete existing lineups
    with pg_conn.cursor() as pg_cur:
        pg_match_ids = list(match_id_map.values())
        placeholders = ','.join(['%s'] * len(pg_match_ids))
        pg_cur.execute(f"""
            DELETE FROM public.match_lineups 
            WHERE match_id IN ({placeholders})
        """, pg_match_ids)
        deleted = pg_cur.rowcount
        print(f"  Deleted {deleted} existing lineups")
    
    pg_conn.commit()
    
    # Sync all lineups
    total_synced = 0
    for sqlite_match_id, pg_match_id in match_id_map.items():
        cur = sqlite_conn.execute("""
            SELECT * FROM match_lineups WHERE match_id = ?
        """, (sqlite_match_id,))
        
        lineups = cur.fetchall()
        synced = 0
        
        with pg_conn.cursor() as pg_cur:
            for lineup in lineups:
                pg_player_id = player_id_map.get(lineup['player_id'])
                pg_team_id = team_id_map.get(lineup['team_id'])
                
                if not pg_player_id or not pg_team_id:
                    print(f"    Warning: Missing mapping for lineup - player_id={lineup['player_id']}, team_id={lineup['team_id']}")
                    continue
                
                pg_cur.execute("""
                    INSERT INTO public.match_lineups (
                        match_id, team_id, player_id, shirt_number, is_starter,
                        minute_on, stoppage_on, minute_off, stoppage_off
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    pg_match_id, pg_team_id, pg_player_id,
                    lineup['shirt_number'],
                    bool(lineup['is_starter']) if lineup['is_starter'] is not None else None,
                    lineup['minute_on'], lineup['stoppage_on'],
                    lineup['minute_off'], lineup['stoppage_off']
                ))
                synced += 1
        
        pg_conn.commit()
        total_synced += synced
        if synced > 0:
            print(f"  Match {pg_match_id}: synced {synced} lineups")
    
    print(f"  ✓ Total lineups synced: {total_synced}")


def main():
    print("=" * 80)
    print("FIX EURO MATCH MAPPING - Complete Sync")
    print("=" * 80)
    print()
    
    sqlite_conn = sqlite3.connect("fsv_archive_complete.db")
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(os.getenv("DB_URL"))
    
    try:
        # Get Euro match IDs
        match_ids = get_euro_match_ids(sqlite_conn)
        print(f"Processing {len(match_ids)} Euro matches: {match_ids}\n")
        
        # Build complete mappings
        player_id_map = build_player_mappings(sqlite_conn, pg_conn, match_ids)
        team_id_map = build_team_mappings(sqlite_conn, pg_conn, match_ids)
        match_id_map = get_postgres_match_mapping(sqlite_conn, pg_conn)
        
        # Re-sync with complete mappings
        resync_goals(sqlite_conn, pg_conn, match_id_map, player_id_map, team_id_map)
        resync_lineups(sqlite_conn, pg_conn, match_id_map, player_id_map, team_id_map)
        
        print("\n" + "=" * 80)
        print("✅ SYNC COMPLETE!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()

