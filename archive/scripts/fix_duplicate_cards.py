"""
Script to fix duplicate cards in the database
Removes duplicates keeping only the first occurrence (lowest card_id)
"""
import psycopg2
from config import Config
from psycopg2.extras import execute_values

def fix_duplicate_cards(dry_run: bool = True):
    """Remove duplicate cards from database"""
    config = Config()
    dsn = config.build_psycopg2_dsn()
    
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            # First, analyze duplicates
            print("=== Analyzing duplicates ===")
            cur.execute('''
                SELECT 
                    COUNT(*) as total_cards,
                    COUNT(DISTINCT (match_id, player_id, COALESCE(minute, -1), card_type)) as unique_cards,
                    COUNT(*) - COUNT(DISTINCT (match_id, player_id, COALESCE(minute, -1), card_type)) as duplicates
                FROM public.cards
                WHERE card_type IN ('yellow', 'second_yellow', 'red')
            ''')
            row = cur.fetchone()
            print(f"Total cards: {row[0]:,}")
            print(f"Unique cards: {row[1]:,}")
            print(f"Duplicates: {row[2]:,}")
            
            if dry_run:
                print("\n=== DRY RUN - No changes made ===")
                print("Call with dry_run=False to actually delete duplicates")
                return
            
            print("\n=== Deleting duplicates ===")
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
            
            # Verify
            cur.execute('''
                SELECT 
                    COUNT(*) as total_cards,
                    COUNT(DISTINCT (match_id, player_id, COALESCE(minute, -1), card_type)) as unique_cards
                FROM public.cards
                WHERE card_type IN ('yellow', 'second_yellow', 'red')
            ''')
            row = cur.fetchone()
            print(f"\nAfter cleanup:")
            print(f"Total cards: {row[0]:,}")
            print(f"Unique cards: {row[1]:,}")
            
            if row[0] == row[1]:
                print("✅ All duplicates removed!")
            else:
                print(f"⚠️  Still {row[0] - row[1]} duplicates remaining")

if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv or "--dry" in sys.argv
    if not dry_run:
        print("WARNING: This will DELETE duplicate cards from the database!")
        print("Run with --dry-run first to see what would be deleted.")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    
    fix_duplicate_cards(dry_run=dry_run)


