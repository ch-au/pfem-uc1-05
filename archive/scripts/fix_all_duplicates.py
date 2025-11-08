"""
Script to fix duplicate records in all tables before applying unique constraints
"""
import psycopg2
from config import Config
from psycopg2.extras import execute_values

def fix_duplicates(dry_run: bool = True):
    """Remove duplicate records from all tables"""
    config = Config()
    dsn = config.build_psycopg2_dsn()
    
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            stats = {}
            
            # 1. Cards
            print("=== Fixing duplicate cards ===")
            cur.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT (match_id, player_id, COALESCE(minute, -1), card_type)) as unique_records,
                    COUNT(*) - COUNT(DISTINCT (match_id, player_id, COALESCE(minute, -1), card_type)) as duplicates
                FROM public.cards
                WHERE card_type IN ('yellow', 'second_yellow', 'red')
            ''')
            row = cur.fetchone()
            print(f"Total cards: {row[0]:,}, Unique: {row[1]:,}, Duplicates: {row[2]:,}")
            stats['cards'] = row[2]
            
            if not dry_run and row[2] > 0:
                # Delete duplicates, keeping only the first (lowest card_id)
                cur.execute('''
                    DELETE FROM public.cards
                    WHERE card_id NOT IN (
                        SELECT MIN(card_id)
                        FROM public.cards
                        GROUP BY match_id, player_id, COALESCE(minute, -1), card_type
                    )
                    AND card_type IN ('yellow', 'second_yellow', 'red')
                ''')
                deleted = cur.rowcount
                conn.commit()
                print(f"Deleted {deleted:,} duplicate cards")
            
            # 2. Goals
            print("\n=== Fixing duplicate goals ===")
            cur.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT (match_id, player_id, minute, COALESCE(stoppage, -1))) as unique_records,
                    COUNT(*) - COUNT(DISTINCT (match_id, player_id, minute, COALESCE(stoppage, -1))) as duplicates
                FROM public.goals
                WHERE player_id IS NOT NULL
            ''')
            row = cur.fetchone()
            print(f"Total goals: {row[0]:,}, Unique: {row[1]:,}, Duplicates: {row[2]:,}")
            stats['goals'] = row[2]
            
            if not dry_run and row[2] > 0:
                cur.execute('''
                    DELETE FROM public.goals
                    WHERE goal_id NOT IN (
                        SELECT MIN(goal_id)
                        FROM public.goals
                        WHERE player_id IS NOT NULL
                        GROUP BY match_id, player_id, minute, COALESCE(stoppage, -1)
                    )
                    AND player_id IS NOT NULL
                ''')
                deleted = cur.rowcount
                conn.commit()
                print(f"Deleted {deleted:,} duplicate goals")
            
            # 3. Match Substitutions
            print("\n=== Fixing duplicate substitutions ===")
            cur.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT (match_id, player_on_id, player_off_id, minute, COALESCE(stoppage, -1))) as unique_records,
                    COUNT(*) - COUNT(DISTINCT (match_id, player_on_id, player_off_id, minute, COALESCE(stoppage, -1))) as duplicates
                FROM public.match_substitutions
            ''')
            row = cur.fetchone()
            print(f"Total substitutions: {row[0]:,}, Unique: {row[1]:,}, Duplicates: {row[2]:,}")
            stats['substitutions'] = row[2]
            
            if not dry_run and row[2] > 0:
                cur.execute('''
                    DELETE FROM public.match_substitutions
                    WHERE substitution_id NOT IN (
                        SELECT MIN(substitution_id)
                        FROM public.match_substitutions
                        GROUP BY match_id, player_on_id, player_off_id, minute, COALESCE(stoppage, -1)
                    )
                ''')
                deleted = cur.rowcount
                conn.commit()
                print(f"Deleted {deleted:,} duplicate substitutions")
            
            # 4. Match Lineups
            print("\n=== Fixing duplicate lineups ===")
            cur.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT (match_id, player_id, team_id)) as unique_records,
                    COUNT(*) - COUNT(DISTINCT (match_id, player_id, team_id)) as duplicates
                FROM public.match_lineups
            ''')
            row = cur.fetchone()
            print(f"Total lineups: {row[0]:,}, Unique: {row[1]:,}, Duplicates: {row[2]:,}")
            stats['lineups'] = row[2]
            
            if not dry_run and row[2] > 0:
                cur.execute('''
                    DELETE FROM public.match_lineups
                    WHERE lineup_id NOT IN (
                        SELECT MIN(lineup_id)
                        FROM public.match_lineups
                        GROUP BY match_id, player_id, team_id
                    )
                ''')
                deleted = cur.rowcount
                conn.commit()
                print(f"Deleted {deleted:,} duplicate lineups")
            
            # 5. Match Coaches
            print("\n=== Fixing duplicate coaches ===")
            cur.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT (match_id, team_id, coach_id, role)) as unique_records,
                    COUNT(*) - COUNT(DISTINCT (match_id, team_id, coach_id, role)) as duplicates
                FROM public.match_coaches
            ''')
            row = cur.fetchone()
            print(f"Total coaches: {row[0]:,}, Unique: {row[1]:,}, Duplicates: {row[2]:,}")
            stats['coaches'] = row[2]
            
            if not dry_run and row[2] > 0:
                cur.execute('''
                    DELETE FROM public.match_coaches
                    WHERE match_coach_id NOT IN (
                        SELECT MIN(match_coach_id)
                        FROM public.match_coaches
                        GROUP BY match_id, team_id, coach_id, role
                    )
                ''')
                deleted = cur.rowcount
                conn.commit()
                print(f"Deleted {deleted:,} duplicate coaches")
            
            # 6. Match Referees
            print("\n=== Fixing duplicate referees ===")
            cur.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT (match_id, referee_id, role)) as unique_records,
                    COUNT(*) - COUNT(DISTINCT (match_id, referee_id, role)) as duplicates
                FROM public.match_referees
            ''')
            row = cur.fetchone()
            print(f"Total referees: {row[0]:,}, Unique: {row[1]:,}, Duplicates: {row[2]:,}")
            stats['referees'] = row[2]
            
            if not dry_run and row[2] > 0:
                cur.execute('''
                    DELETE FROM public.match_referees
                    WHERE match_referee_id NOT IN (
                        SELECT MIN(match_referee_id)
                        FROM public.match_referees
                        GROUP BY match_id, referee_id, role
                    )
                ''')
                deleted = cur.rowcount
                conn.commit()
                print(f"Deleted {deleted:,} duplicate referees")
            
            print("\n=== Summary ===")
            total_duplicates = sum(stats.values())
            print(f"Total duplicates found: {total_duplicates:,}")
            for table, count in stats.items():
                if count > 0:
                    print(f"  {table}: {count:,}")
            
            if dry_run:
                print("\n=== DRY RUN - No changes made ===")
                print("Call with dry_run=False to actually delete duplicates")
            else:
                print("\n=== Cleanup complete ===")
                print("You can now run database/add_unique_constraints.sql")

if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv or "--dry" in sys.argv
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv
    
    if not dry_run and not auto_confirm:
        print("WARNING: This will DELETE duplicate records from the database!")
        print("Run with --dry-run first to see what would be deleted.")
        print("Use --yes to skip confirmation.")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    
    fix_duplicates(dry_run=dry_run)


