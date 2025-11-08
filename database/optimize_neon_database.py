#!/usr/bin/env python3
"""
Optimize Neon Database with Indexes and Materialized Views

This script applies performance optimizations to the Neon PostgreSQL database:
- Creates missing indexes for chat tables
- Creates additional indexes for football database queries
- Creates materialized views for common query patterns
- Refreshes existing materialized views

Usage:
    python optimize_neon_database.py
    python optimize_neon_database.py --refresh-only  # Only refresh materialized views
    python optimize_neon_database.py --dry-run       # Show what would be executed
"""

import argparse
import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def read_sql_file(file_path: Path) -> str:
    """Read SQL file content"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def execute_sql_statements(conn, sql_content: str, dry_run: bool = False):
    """Execute SQL statements, handling errors gracefully"""
    statements = []
    current_statement = []
    
    # Split SQL into individual statements
    for line in sql_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('--'):
            continue
        
        current_statement.append(line)
        
        if line.endswith(';'):
            statement = ' '.join(current_statement)
            if statement:
                statements.append(statement)
            current_statement = []
    
    if dry_run:
        print(f"Would execute {len(statements)} SQL statements:")
        for i, stmt in enumerate(statements[:5], 1):  # Show first 5
            print(f"  {i}. {stmt[:100]}...")
        if len(statements) > 5:
            print(f"  ... and {len(statements) - 5} more")
        return
    
    executed = 0
    errors = 0
    
    with conn.cursor() as cur:
        for statement in statements:
            try:
                cur.execute(statement)
                executed += 1
            except Exception as e:
                # Some errors are expected (e.g., "already exists")
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'does not exist' in error_msg:
                    # These are expected, don't count as errors
                    pass
                else:
                    errors += 1
                    print(f"  ⚠️  Error: {e}")
                    print(f"     Statement: {statement[:100]}...")
        
        conn.commit()
    
    return executed, errors


def check_index_exists(conn, index_name: str) -> bool:
    """Check if an index exists"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND indexname = %s
            )
        """, (index_name,))
        return cur.fetchone()[0]


def check_materialized_view_exists(conn, view_name: str) -> bool:
    """Check if a materialized view exists"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_matviews 
                WHERE schemaname = 'public' 
                AND matviewname = %s
            )
        """, (view_name,))
        return cur.fetchone()[0]


def refresh_materialized_views(conn, dry_run: bool = False):
    """Refresh all materialized views"""
    views = [
        'player_statistics',
        'match_details',
        'season_summary',
        'top_scorers',
        'match_results_summary',
        'player_season_stats'
    ]
    
    print("\n" + "=" * 80)
    print("REFRESH MATERIALIZED VIEWS")
    print("=" * 80)
    
    refreshed = 0
    skipped = 0
    
    for view_name in views:
        exists = check_materialized_view_exists(conn, view_name)
        
        if not exists:
            print(f"  ⏭️  {view_name}: Does not exist, skipping")
            skipped += 1
            continue
        
        if dry_run:
            print(f"  🔄 Would refresh: {view_name}")
            refreshed += 1
            continue
        
        try:
            with conn.cursor() as cur:
                cur.execute(f"REFRESH MATERIALIZED VIEW public.{view_name}")
                conn.commit()
                print(f"  ✓ Refreshed: {view_name}")
                refreshed += 1
        except Exception as e:
            print(f"  ⚠️  Error refreshing {view_name}: {e}")
    
    print(f"\n  Refreshed: {refreshed}, Skipped: {skipped}")
    return refreshed


def main():
    parser = argparse.ArgumentParser(
        description='Optimize Neon Database with Indexes and Materialized Views'
    )
    parser.add_argument(
        '--refresh-only',
        action='store_true',
        help='Only refresh materialized views, skip creating indexes/views'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be executed without actually executing'
    )
    args = parser.parse_args()
    
    # Get database URL
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("❌ Error: DB_URL environment variable not set")
        print("   Please set DB_URL in your .env file or environment")
        sys.exit(1)
    
    print("=" * 80)
    print("NEON DATABASE OPTIMIZATION")
    print("=" * 80)
    print()
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else 'Connected'}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()
    
    try:
        conn = psycopg2.connect(db_url)
        print("✓ Connected to database")
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)
    
    try:
        if not args.refresh_only:
            # Read and execute optimization SQL
            sql_file = Path(__file__).parent / "optimize_neon_database.sql"
            
            if not sql_file.exists():
                print(f"❌ Error: SQL file not found: {sql_file}")
                sys.exit(1)
            
            print("\n" + "=" * 80)
            print("APPLYING INDEXES AND MATERIALIZED VIEWS")
            print("=" * 80)
            print()
            
            sql_content = read_sql_file(sql_file)
            
            # Remove REFRESH statements (we'll do those separately)
            sql_content_clean = []
            skip_refresh = False
            for line in sql_content.split('\n'):
                if 'REFRESH MATERIALIZED VIEW' in line.upper():
                    skip_refresh = True
                    continue
                if skip_refresh and line.strip() == '':
                    skip_refresh = False
                    continue
                if not skip_refresh:
                    sql_content_clean.append(line)
            
            sql_content = '\n'.join(sql_content_clean)
            
            execute_sql_statements(conn, sql_content, dry_run=args.dry_run)
            
            if not args.dry_run:
                print("\n✓ Indexes and materialized views created")
        
        # Refresh materialized views
        refresh_materialized_views(conn, dry_run=args.dry_run)
        
        # Show statistics
        if not args.dry_run:
            print("\n" + "=" * 80)
            print("DATABASE STATISTICS")
            print("=" * 80)
            print()
            
            with conn.cursor() as cur:
                # Count indexes
                cur.execute("""
                    SELECT COUNT(*) FROM pg_indexes 
                    WHERE schemaname = 'public'
                """)
                index_count = cur.fetchone()[0]
                print(f"  Total indexes: {index_count}")
                
                # Count materialized views
                cur.execute("""
                    SELECT COUNT(*) FROM pg_matviews 
                    WHERE schemaname = 'public'
                """)
                mv_count = cur.fetchone()[0]
                print(f"  Materialized views: {mv_count}")
                
                # Show materialized view row counts
                cur.execute("""
                    SELECT matviewname FROM pg_matviews 
                    WHERE schemaname = 'public'
                    ORDER BY matviewname
                """)
                views = [row[0] for row in cur.fetchall()]
                
                if views:
                    print("\n  Materialized view sizes:")
                    for view_name in views:
                        try:
                            cur.execute(f"SELECT COUNT(*) FROM public.{view_name}")
                            count = cur.fetchone()[0]
                            print(f"    {view_name}: {count:,} rows")
                        except:
                            pass
        
        print("\n" + "=" * 80)
        print("✅ OPTIMIZATION COMPLETE")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Monitor query performance")
        print("  2. Refresh materialized views periodically:")
        print("     python optimize_neon_database.py --refresh-only")
        print()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()
        print("✓ Database connection closed")


if __name__ == "__main__":
    main()



