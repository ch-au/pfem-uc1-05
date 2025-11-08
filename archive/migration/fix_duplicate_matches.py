#!/usr/bin/env python3
"""
Fix duplicate matches in the database.

The issue: Same matches appear twice with different team name variations
(e.g., "FSV" vs "1. FSV Mainz 05")

This script:
1. Identifies duplicate matches (same date, teams, score)
2. Consolidates to one canonical match (prefer "1. FSV Mainz 05")
3. Removes duplicates

Usage:
    python fix_duplicate_matches.py --dry-run
    python fix_duplicate_matches.py
"""

import argparse
import os
import sys
from typing import List, Tuple
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def find_duplicate_matches(pg_conn):
    """Find duplicate matches."""
    print("Searching for duplicate matches...")
    
    with pg_conn.cursor() as cur:
        # Find matches with same date, teams, and score
        cur.execute("""
            WITH match_keys AS (
                SELECT 
                    m.match_id,
                    m.match_date,
                    LEAST(t_home.normalized_name, t_away.normalized_name) as team1,
                    GREATEST(t_home.normalized_name, t_away.normalized_name) as team2,
                    LEAST(m.home_score, m.away_score) as score1,
                    GREATEST(m.home_score, m.away_score) as score2,
                    t_home.name as home_name,
                    t_away.name as away_name,
                    m.home_score,
                    m.away_score
                FROM public.matches m
                JOIN public.teams t_home ON m.home_team_id = t_home.team_id
                JOIN public.teams t_away ON m.away_team_id = t_away.team_id
                WHERE m.match_date IS NOT NULL
            )
            SELECT 
                match_date,
                team1,
                team2,
                score1,
                score2,
                ARRAY_AGG(match_id ORDER BY 
                    CASE 
                        WHEN home_name LIKE '%1. FSV Mainz%' OR away_name LIKE '%1. FSV Mainz%' THEN 0
                        ELSE 1
                    END,
                    match_id
                ) as match_ids,
                ARRAY_AGG(home_name || ' ' || home_score::TEXT || ':' || away_score::TEXT || ' ' || away_name ORDER BY match_id) as match_details
            FROM match_keys
            GROUP BY match_date, team1, team2, score1, score2
            HAVING COUNT(*) > 1
            ORDER BY match_date DESC
            LIMIT 50
        """)
        
        duplicates = cur.fetchall()
        
        if duplicates:
            print(f"\n🔍 Found {len(duplicates)} sets of duplicate matches:\n")
            for dup in duplicates[:10]:
                date, team1, team2, score1, score2, match_ids, details = dup
                print(f"Date: {date} | Teams: {team1} vs {team2} | Score: {score1}:{score2}")
                print(f"  Match IDs: {match_ids}")
                for detail in details:
                    print(f"    - {detail}")
                print()
            
            if len(duplicates) > 10:
                print(f"... and {len(duplicates) - 10} more duplicate sets\n")
        else:
            print("✓ No duplicates found")
        
        return duplicates


def remove_duplicates(pg_conn, duplicates, dry_run=False):
    """Remove duplicate matches, keeping the preferred one."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Removing duplicates...")
    
    total_to_delete = 0
    deleted_ids = []
    
    for dup in duplicates:
        match_ids = dup[5]  # array of match IDs
        
        # Keep the first one (preferred by our ORDER BY), delete the rest
        keep_id = match_ids[0]
        delete_ids = match_ids[1:]
        
        total_to_delete += len(delete_ids)
        deleted_ids.extend(delete_ids)
    
    print(f"  Will keep {len(duplicates)} matches")
    print(f"  Will delete {total_to_delete} duplicate matches")
    
    if dry_run:
        print(f"\n[DRY RUN] Would delete these match IDs: {deleted_ids[:20]}")
        if len(deleted_ids) > 20:
            print(f"  ... and {len(deleted_ids) - 20} more")
        return
    
    # Actually delete
    with pg_conn.cursor() as cur:
        placeholders = ','.join(['%s'] * len(deleted_ids))
        
        # Delete will CASCADE to related tables (goals, lineups, cards, subs)
        cur.execute(f"""
            DELETE FROM public.matches
            WHERE match_id IN ({placeholders})
        """, deleted_ids)
        
        deleted_count = cur.rowcount
        print(f"  ✓ Deleted {deleted_count} duplicate matches")
    
    pg_conn.commit()
    
    return deleted_ids


def verify_fix(pg_conn):
    """Verify that duplicates have been removed."""
    print("\nVerifying fix...")
    
    with pg_conn.cursor() as cur:
        # Check 2016-17 Bundesliga count
        cur.execute("""
            SELECT COUNT(*)
            FROM public.matches m
            JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
            JOIN public.competitions c ON sc.competition_id = c.competition_id
            JOIN public.seasons s ON sc.season_id = s.season_id
            WHERE c.name = 'Bundesliga' AND s.label = '2016-17'
        """)
        
        count = cur.fetchone()[0]
        print(f"  2016-17 Bundesliga now has: {count} matches")
        
        if count == 34:
            print("  ✅ CORRECT - exactly 34 matches!")
        elif count == 68:
            print("  ❌ Still 68 matches - duplicates not removed")
        else:
            print(f"  ⚠️  Unexpected count: {count}")


def main():
    parser = argparse.ArgumentParser(description="Fix duplicate matches")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()
    
    print("=" * 80)
    print("DUPLICATE MATCH REMOVAL")
    print("=" * 80)
    if args.dry_run:
        print("MODE: DRY RUN\n")
    else:
        print("MODE: LIVE\n")
    
    try:
        pg_conn = psycopg2.connect(os.getenv("DB_URL"))
        
        duplicates = find_duplicate_matches(pg_conn)
        
        if duplicates:
            remove_duplicates(pg_conn, duplicates, dry_run=args.dry_run)
            
            if not args.dry_run:
                verify_fix(pg_conn)
        
        pg_conn.close()
        
        print("\n" + "=" * 80)
        if args.dry_run:
            print("DRY RUN COMPLETE")
        else:
            print("✅ DUPLICATES REMOVED")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

