#!/usr/bin/env python3
"""
Remove Bundesliga duplicate matches with near-duplicate dates.

The issue: Same matches appear with dates off by 1 day (different data sources).

Strategy:
1. Group by season, opponent, and score
2. If multiple matches found, keep the one with MORE data (lineups, goals)
3. Delete the others

Usage:
    python remove_bundesliga_duplicates.py --dry-run
    python remove_bundesliga_duplicates.py
"""

import argparse
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def find_duplicates_by_opponent(pg_conn, season_label='2016-17', competition='Bundesliga'):
    """Find duplicate matches by grouping by opponent and score."""
    print(f"Finding duplicates in {season_label} {competition}...")
    
    duplicates_to_remove = []
    
    with pg_conn.cursor() as cur:
        # Find home match duplicates
        cur.execute("""
            SELECT 
                t_away.name as opponent,
                m.home_score,
                m.away_score,
                ARRAY_AGG(m.match_id ORDER BY m.match_id) as match_ids,
                ARRAY_AGG(m.match_date::TEXT ORDER BY m.match_id) as dates,
                ARRAY_AGG(
                    (SELECT COUNT(*) FROM public.match_lineups WHERE match_id = m.match_id)
                    ORDER BY m.match_id
                ) as lineup_counts
            FROM public.matches m
            JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
            JOIN public.competitions c ON sc.competition_id = c.competition_id
            JOIN public.seasons s ON sc.season_id = s.season_id
            JOIN public.teams t_home ON m.home_team_id = t_home.team_id
            JOIN public.teams t_away ON m.away_team_id = t_away.team_id
            WHERE c.name = %s
            AND s.label = %s
            AND t_home.team_id = 1  -- FSV Mainz home
            GROUP BY t_away.name, m.home_score, m.away_score
            HAVING COUNT(*) > 1
        """, (competition, season_label))
        
        home_dups = cur.fetchall()
        
        # Find away match duplicates  
        cur.execute("""
            SELECT 
                t_home.name as opponent,
                m.home_score,
                m.away_score,
                ARRAY_AGG(m.match_id ORDER BY m.match_id) as match_ids,
                ARRAY_AGG(m.match_date::TEXT ORDER BY m.match_id) as dates,
                ARRAY_AGG(
                    (SELECT COUNT(*) FROM public.match_lineups WHERE match_id = m.match_id)
                    ORDER BY m.match_id
                ) as lineup_counts
            FROM public.matches m
            JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
            JOIN public.competitions c ON sc.competition_id = c.competition_id
            JOIN public.seasons s ON sc.season_id = s.season_id
            JOIN public.teams t_home ON m.home_team_id = t_home.team_id
            JOIN public.teams t_away ON m.away_team_id = t_away.team_id
            WHERE c.name = %s
            AND s.label = %s
            AND t_away.team_id = 1  -- FSV Mainz away
            GROUP BY t_home.name, m.home_score, m.away_score
            HAVING COUNT(*) > 1
        """, (competition, season_label))
        
        away_dups = cur.fetchall()
    
    print(f"\n  Home match duplicates: {len(home_dups)}")
    print(f"  Away match duplicates: {len(away_dups)}")
    
    # Process duplicates
    for dup in home_dups + away_dups:
        opponent, h_score, a_score, match_ids, dates, lineup_counts = dup
        
        # Keep the match with most lineups (most complete data)
        max_lineups = max(lineup_counts)
        keep_idx = lineup_counts.index(max_lineups)
        keep_id = match_ids[keep_idx]
        
        delete_ids = [mid for i, mid in enumerate(match_ids) if i != keep_idx]
        
        if delete_ids:
            duplicates_to_remove.extend(delete_ids)
            print(f"\n  {opponent} ({h_score}:{a_score}):")
            print(f"    Keep:   Match {keep_id} (date: {dates[keep_idx]}, {lineup_counts[keep_idx]} lineups)")
            print(f"    Delete: {delete_ids} (dates: {[dates[i] for i, _ in enumerate(match_ids) if i != keep_idx]})")
    
    return duplicates_to_remove


def delete_matches(pg_conn, match_ids, dry_run=False):
    """Delete the specified matches."""
    if not match_ids:
        print("\n✓ No duplicates to remove")
        return
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Removing {len(match_ids)} duplicate matches...")
    
    if dry_run:
        print(f"  [DRY RUN] Would delete match IDs: {match_ids}")
        return
    
    with pg_conn.cursor() as cur:
        placeholders = ','.join(['%s'] * len(match_ids))
        cur.execute(f"""
            DELETE FROM public.matches
            WHERE match_id IN ({placeholders})
        """, match_ids)
        
        deleted = cur.rowcount
        print(f"  ✓ Deleted {deleted} matches")
    
    pg_conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Remove Bundesliga duplicate matches")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--season", default="2016-17", help="Season to check")
    args = parser.parse_args()
    
    print("=" * 80)
    print(f"REMOVE BUNDESLIGA DUPLICATES - {args.season}")
    print("=" * 80)
    if args.dry_run:
        print("MODE: DRY RUN\n")
    else:
        print("MODE: LIVE\n")
    
    try:
        pg_conn = psycopg2.connect(os.getenv("DB_URL"))
        
        duplicates = find_duplicates_by_opponent(pg_conn, season_label=args.season)
        delete_matches(pg_conn, duplicates, dry_run=args.dry_run)
        
        # Verify
        if not args.dry_run and duplicates:
            with pg_conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM public.matches m
                    JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                    JOIN public.competitions c ON sc.competition_id = c.competition_id
                    JOIN public.seasons s ON sc.season_id = s.season_id
                    WHERE c.name = 'Bundesliga' AND s.label = %s
                """, (args.season,))
                
                count = cur.fetchone()[0]
                print(f"\n✓ {args.season} Bundesliga now has: {count} matches")
                if count == 34:
                    print("  ✅ PERFECT!")
        
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

