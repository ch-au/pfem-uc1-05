#!/usr/bin/env python3
"""
Consolidate ALL FSV Mainz team variants into team_id = 1.

Problem: Database has multiple team entries for FSV Mainz variants:
  - Team ID 1: "1. FSV Mainz 05" (should be the main one)
  - Team ID 3: "1. Mainzer FC Hassia 05"
  - Team ID 5: "FC Viktoria 05 Mainz"
  - Team ID 15: "1. Mainzer FC Hassia-Hermania 05"
  - Team ID 17: "1. Mainzer FV 05"
  - Team ID 20: "1. Mainzer FSV 05"
  - Team ID 79: "Reichsbahn TSV Mainz 05"
  - etc.

This script:
1. Finds all Mainz team variants
2. Merges all references to team_id = 1
3. Updates all foreign key references in all tables
4. Deletes duplicate teams

Usage:
    python consolidate_all_mainz_teams.py --dry-run
    python consolidate_all_mainz_teams.py
"""

import argparse
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def find_mainz_teams(pg_conn):
    """Find all Mainz team variants."""
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT 
                team_id,
                name,
                normalized_name,
                COUNT(DISTINCT m.match_id) as matches
            FROM public.teams t
            LEFT JOIN public.matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            WHERE t.name ILIKE '%mainz%' AND (t.name ILIKE '%05%' OR t.name ILIKE '%fsv%')
            GROUP BY t.team_id, t.name, t.normalized_name
            ORDER BY matches DESC
        """)
        return cur.fetchall()


def analyze_consolidation(pg_conn, mainz_teams, target_team_id=1):
    """Analyze what would be consolidated."""
    print("Analyzing consolidation...")
    print(f"\nFound {len(mainz_teams)} Mainz team variants:")
    print("-" * 80)
    
    total_updates = {}
    
    with pg_conn.cursor() as cur:
        # Check if target team exists
        cur.execute("SELECT name FROM public.teams WHERE team_id = %s", (target_team_id,))
        target_team = cur.fetchone()
        if not target_team:
            print(f"❌ ERROR: Target team_id {target_team_id} does not exist!")
            return None
        
        print(f"✅ Target team: team_id={target_team_id} = '{target_team[0]}'")
        print()
        
        # Tables to update
        tables_to_check = [
            ("matches", "home_team_id", "home matches"),
            ("matches", "away_team_id", "away matches"),
            ("match_lineups", "team_id", "lineups"),
            ("match_coaches", "team_id", "coach assignments"),
            ("goals", "team_id", "goals"),
            ("cards", "team_id", "cards"),
            ("match_substitutions", "team_id", "substitutions"),
            ("seasons", "team_id", "season assignments"),
        ]
        
        for team_id, name, norm_name, matches in mainz_teams:
            if team_id == target_team_id:
                print(f"  team_id={team_id:3d}: {name:45s} → KEEP (target team)")
                continue
            
            print(f"  team_id={team_id:3d}: {name:45s} → {matches:5d} matches")
            
            for table, column, desc in tables_to_check:
                if table == "matches":
                    if column == "home_team_id":
                        cur.execute(f"SELECT COUNT(*) FROM public.{table} WHERE {column} = %s", (team_id,))
                    else:
                        cur.execute(f"SELECT COUNT(*) FROM public.{table} WHERE {column} = %s", (team_id,))
                else:
                    cur.execute(f"SELECT COUNT(*) FROM public.{table} WHERE {column} = %s", (team_id,))
                
                count = cur.fetchone()[0]
                if count > 0:
                    key = f"{table}.{column}"
                    if key not in total_updates:
                        total_updates[key] = 0
                    total_updates[key] += count
                    print(f"      {desc:25s}: {count:6d} in {table}")
        
        print(f"\n📊 Total updates needed:")
        for key, count in sorted(total_updates.items()):
            print(f"  {key:30s}: {count:6d}")
        
        return total_updates


def consolidate_teams(pg_conn, mainz_teams, target_team_id=1, dry_run=False):
    """Consolidate all Mainz teams into target_team_id."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Consolidating Mainz teams...")
    
    teams_to_merge = [tid for tid, _, _, _ in mainz_teams if tid != target_team_id]
    
    if not teams_to_merge:
        print("  No teams to merge!")
        return
    
    print(f"  Merging {len(teams_to_merge)} teams into team_id={target_team_id}")
    
    tables_to_update = [
        ("matches", "home_team_id", "home matches"),
        ("matches", "away_team_id", "away matches"),
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
            for team_id in teams_to_merge:
                if dry_run:
                    cur.execute(f"SELECT COUNT(*) FROM public.{table} WHERE {column} = %s", (team_id,))
                    count = cur.fetchone()[0]
                    if count > 0:
                        print(f"  [DRY RUN] Would update {count} {desc} in {table} (team_id {team_id} → {target_team_id})")
                        total_updated += count
                else:
                    cur.execute(f"""
                        UPDATE public.{table}
                        SET {column} = %s
                        WHERE {column} = %s
                    """, (target_team_id, team_id))
                    count = cur.rowcount
                    if count > 0:
                        print(f"  ✓ Updated {count} {desc} in {table} (team_id {team_id} → {target_team_id})")
                        total_updated += count
    
    if not dry_run:
        pg_conn.commit()
    
    print(f"\n  Total references updated: {total_updated}")
    
    # Delete merged teams
    if not dry_run:
        print(f"\nDeleting merged teams...")
        with pg_conn.cursor() as cur:
            for team_id in teams_to_merge:
                cur.execute("DELETE FROM public.teams WHERE team_id = %s", (team_id,))
                print(f"  ✓ Deleted team_id={team_id}")
        pg_conn.commit()


def verify_consolidation(pg_conn, target_team_id=1):
    """Verify that consolidation was successful."""
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    with pg_conn.cursor() as cur:
        # Check remaining Mainz teams
        cur.execute("""
            SELECT 
                team_id,
                name,
                COUNT(DISTINCT m.match_id) as matches
            FROM public.teams t
            LEFT JOIN public.matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            WHERE t.name ILIKE '%mainz%' AND (t.name ILIKE '%05%' OR t.name ILIKE '%fsv%')
            GROUP BY t.team_id, t.name
            ORDER BY matches DESC
        """)
        
        remaining = cur.fetchall()
        print(f"\nRemaining Mainz teams: {len(remaining)}")
        for tid, name, matches in remaining:
            marker = " *** MAIN TEAM ***" if tid == target_team_id else ""
            print(f"  team_id={tid:3d}: {name:45s} → {matches:5d} matches{marker}")
        
        # Check total matches for target team
        cur.execute("""
            SELECT COUNT(*) 
            FROM public.matches 
            WHERE home_team_id = %s OR away_team_id = %s
        """, (target_team_id, target_team_id))
        total_matches = cur.fetchone()[0]
        print(f"\n✅ Total matches for team_id={target_team_id}: {total_matches:,}")


def main():
    parser = argparse.ArgumentParser(description="Consolidate all FSV Mainz team variants")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--target-id", type=int, default=1, help="Target team_id to merge into (default: 1)")
    args = parser.parse_args()
    
    print("=" * 80)
    print("CONSOLIDATE ALL FSV MAINZ TEAM VARIANTS")
    print("=" * 80)
    if args.dry_run:
        print("MODE: DRY RUN\n")
    else:
        print("MODE: LIVE\n")
    
    try:
        pg_conn = psycopg2.connect(os.getenv("DB_URL"))
        
        # Find all Mainz teams
        mainz_teams = find_mainz_teams(pg_conn)
        
        if not mainz_teams:
            print("No Mainz teams found!")
            return
        
        # Analyze
        analyze_consolidation(pg_conn, mainz_teams, args.target_id)
        
        # Consolidate
        consolidate_teams(pg_conn, mainz_teams, args.target_id, dry_run=args.dry_run)
        
        # Verify
        if not args.dry_run:
            verify_consolidation(pg_conn, args.target_id)
        
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

