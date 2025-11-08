#!/usr/bin/env python3
"""
Consolidate duplicate FSV Mainz team entries.

Problem: Database has TWO team entries for FSV Mainz:
  - Team ID 1: "1. FSV Mainz 05"
  - Team ID 36: "FSV"

This causes duplicate matches. This script:
1. Merges all "FSV" (ID 36) references to "1. FSV Mainz 05" (ID 1)
2. Deletes duplicate matches
3. Updates all foreign key references

Usage:
    python consolidate_fsv_team.py --dry-run
    python consolidate_fsv_team.py
"""

import argparse
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def analyze_duplication(pg_conn):
    """Analyze the extent of duplication."""
    print("Analyzing duplication...")
    
    with pg_conn.cursor() as cur:
        # Check matches using each team ID
        for team_id, team_name in [(1, "1. FSV Mainz 05"), (36, "FSV")]:
            cur.execute("""
                SELECT COUNT(*) 
                FROM public.matches m
                WHERE m.home_team_id = %s OR m.away_team_id = %s
            """, (team_id, team_id))
            count = cur.fetchone()[0]
            print(f"  Team {team_id} '{team_name}': {count} matches")
        
        # Check other tables
        tables_to_check = [
            ("match_lineups", "team_id"),
            ("match_coaches", "team_id"),
            ("goals", "team_id"),
            ("cards", "team_id"),
            ("match_substitutions", "team_id"),
        ]
        
        print(f"\n  Other references to Team ID 36 ('FSV'):")
        for table, column in tables_to_check:
            cur.execute(f"SELECT COUNT(*) FROM public.{table} WHERE {column} = 36")
            count = cur.fetchone()[0]
            if count > 0:
                print(f"    {table}: {count} records")


def merge_team_ids(pg_conn, dry_run=False):
    """Merge Team ID 36 into Team ID 1."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Merging FSV team IDs...")
    
    tables_to_update = [
        # Format: (table, column, description)
        ("match_lineups", "team_id", "lineups"),
        ("match_coaches", "team_id", "coach assignments"),
        ("goals", "team_id", "goals"),
        ("cards", "team_id", "cards"),
        ("match_substitutions", "team_id", "substitutions"),
        ("seasons", "team_id", "season assignments"),
    ]
    
    total_updated = 0
    
    with pg_conn.cursor() as cur:
        for table, column, desc in tables_to_update:
            if dry_run:
                cur.execute(f"SELECT COUNT(*) FROM public.{table} WHERE {column} = 36")
                count = cur.fetchone()[0]
                if count > 0:
                    print(f"  [DRY RUN] Would update {count} {desc} in {table}")
                    total_updated += count
            else:
                cur.execute(f"""
                    UPDATE public.{table}
                    SET {column} = 1
                    WHERE {column} = 36
                """)
                count = cur.rowcount
                if count > 0:
                    print(f"  ✓ Updated {count} {desc} in {table}")
                    total_updated += count
        
        # Update matches (both home and away)
        if dry_run:
            cur.execute("SELECT COUNT(*) FROM public.matches WHERE home_team_id = 36")
            home_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM public.matches WHERE away_team_id = 36")
            away_count = cur.fetchone()[0]
            print(f"  [DRY RUN] Would update {home_count} home matches")
            print(f"  [DRY RUN] Would update {away_count} away matches")
            total_updated += home_count + away_count
        else:
            cur.execute("UPDATE public.matches SET home_team_id = 1 WHERE home_team_id = 36")
            home_count = cur.rowcount
            cur.execute("UPDATE public.matches SET away_team_id = 1 WHERE away_team_id = 36")
            away_count = cur.rowcount
            print(f"  ✓ Updated {home_count} home matches")
            print(f"  ✓ Updated {away_count} away matches")
            total_updated += home_count + away_count
    
    if not dry_run:
        pg_conn.commit()
    
    print(f"\n  Total references updated: {total_updated}")


def remove_duplicate_matches(pg_conn, dry_run=False):
    """After merging team IDs, remove the resulting duplicate matches."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Removing duplicate matches...")
    
    with pg_conn.cursor() as cur:
        # Find duplicates (now that both use Team ID 1)
        cur.execute("""
            WITH duplicates AS (
                SELECT 
                    m.match_id,
                    m.match_date,
                    m.home_team_id,
                    m.away_team_id,
                    m.home_score,
                    m.away_score,
                    ROW_NUMBER() OVER (
                        PARTITION BY m.season_competition_id, m.match_date, m.home_team_id, m.away_team_id
                        ORDER BY m.match_id
                    ) as rn
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                WHERE c.name = 'Bundesliga' AND s.label = '2016-17'
            )
            SELECT match_id FROM duplicates WHERE rn > 1
        """)
        
        duplicate_ids = [row[0] for row in cur.fetchall()]
        
        if not duplicate_ids:
            print("  No duplicates found after team ID merge")
            return
        
        print(f"  Found {len(duplicate_ids)} duplicate matches to delete")
        
        if dry_run:
            print(f"  [DRY RUN] Would delete match IDs: {duplicate_ids}")
            return
        
        # Delete duplicates (will CASCADE to related tables)
        placeholders = ','.join(['%s'] * len(duplicate_ids))
        cur.execute(f"""
            DELETE FROM public.matches
            WHERE match_id IN ({placeholders})
        """, duplicate_ids)
        
        deleted_count = cur.rowcount
        print(f"  ✓ Deleted {deleted_count} duplicate matches")
        
        pg_conn.commit()


def delete_unused_team(pg_conn, dry_run=False):
    """Delete the unused FSV team entry (ID 36)."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Deleting unused team entry...")
    
    with pg_conn.cursor() as cur:
        # Verify it's not referenced anymore
        cur.execute("""
            SELECT COUNT(*) FROM public.matches 
            WHERE home_team_id = 36 OR away_team_id = 36
        """)
        match_count = cur.fetchone()[0]
        
        if match_count > 0:
            print(f"  ⚠️  Cannot delete - still referenced in {match_count} matches")
            return
        
        if dry_run:
            print("  [DRY RUN] Would delete Team ID 36 'FSV'")
            return
        
        cur.execute("DELETE FROM public.teams WHERE team_id = 36")
        print(f"  ✓ Deleted team ID 36 'FSV'")
        pg_conn.commit()


def verify_consolidation(pg_conn):
    """Verify the consolidation was successful."""
    print("\nVerifying consolidation...")
    
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
        
        print(f"  2016-17 Bundesliga matches: {count}")
        if count == 34:
            print("  ✅ PERFECT - exactly 34 matches!")
        else:
            print(f"  ⚠️  Expected 34, got {count}")
        
        # Check if Team ID 36 still exists
        cur.execute("SELECT COUNT(*) FROM public.teams WHERE team_id = 36")
        team_exists = cur.fetchone()[0]
        
        if team_exists:
            print("  ⚠️  Team ID 36 'FSV' still exists")
        else:
            print("  ✓ Team ID 36 removed")
        
        # Check total Mainz matches
        cur.execute("""
            SELECT COUNT(*)
            FROM public.matches m
            JOIN public.teams t_home ON m.home_team_id = t_home.team_id
            JOIN public.teams t_away ON m.away_team_id = t_away.team_id
            WHERE t_home.name LIKE '%Mainz%' OR t_away.name LIKE '%Mainz%'
        """)
        total = cur.fetchone()[0]
        print(f"  Total FSV Mainz matches across all seasons: {total:,}")


def main():
    parser = argparse.ArgumentParser(description="Consolidate FSV Mainz team duplicates")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()
    
    print("=" * 80)
    print("CONSOLIDATE FSV MAINZ TEAM DUPLICATES")
    print("=" * 80)
    if args.dry_run:
        print("MODE: DRY RUN\n")
    else:
        print("MODE: LIVE\n")
    
    try:
        pg_conn = psycopg2.connect(os.getenv("DB_URL"))
        
        analyze_duplication(pg_conn)
        merge_team_ids(pg_conn, dry_run=args.dry_run)
        remove_duplicate_matches(pg_conn, dry_run=args.dry_run)
        delete_unused_team(pg_conn, dry_run=args.dry_run)
        
        if not args.dry_run:
            verify_consolidation(pg_conn)
        
        pg_conn.close()
        
        print("\n" + "=" * 80)
        if args.dry_run:
            print("DRY RUN COMPLETE")
        else:
            print("✅ CONSOLIDATION COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

