#!/usr/bin/env python3
"""
Apply Performance Optimizations to Neon Database

This script applies the performance optimizations defined in
migration 003_performance_optimizations.sql

Usage:
    python database/apply_optimizations.py

    Or with custom database URL:
    python database/apply_optimizations.py --db-url "postgresql://..."
"""

import os
import sys
import argparse
import psycopg2
from psycopg2 import sql
from datetime import datetime


def get_database_url():
    """Get database URL from environment or argument"""
    return os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/fsv05?sslmode=require')


def connect_to_database(db_url):
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(db_url)
        print("✅ Connected to database")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)


def execute_sql_file(conn, filepath):
    """Execute SQL file with progress feedback"""
    print(f"\n📄 Executing {filepath}...")

    try:
        with open(filepath, 'r') as f:
            sql_content = f.read()

        cursor = conn.cursor()

        # Split by major sections and execute
        sections = sql_content.split('-- ============================================================================')

        for i, section in enumerate(sections):
            if section.strip():
                try:
                    cursor.execute(section)
                    conn.commit()
                except Exception as e:
                    # Some commands may fail if already exist, that's OK
                    if 'already exists' in str(e):
                        print(f"  ℹ️  Skipping existing object: {str(e)[:100]}")
                        conn.rollback()
                    else:
                        print(f"  ⚠️  Warning in section {i}: {str(e)[:200]}")
                        conn.rollback()

        cursor.close()
        print(f"✅ Completed {filepath}")

    except FileNotFoundError:
        print(f"❌ File not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error executing SQL file: {e}")
        sys.exit(1)


def refresh_materialized_views(conn):
    """Refresh all materialized views"""
    print("\n🔄 Refreshing materialized views...")

    views = [
        'top_scorers',
        'match_results_summary',
        'player_season_stats',
        'quiz_global_leaderboard',
        'recent_matches',
        'player_career_highlights',
    ]

    cursor = conn.cursor()

    for view in views:
        try:
            print(f"  Refreshing {view}...")
            start = datetime.now()

            # Check if view exists
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = %s)",
                (view,)
            )
            exists = cursor.fetchone()[0]

            if exists:
                cursor.execute(sql.SQL("REFRESH MATERIALIZED VIEW CONCURRENTLY public.{}").format(
                    sql.Identifier(view)
                ))
                conn.commit()
                duration = (datetime.now() - start).total_seconds()
                print(f"  ✅ Refreshed {view} in {duration:.2f}s")
            else:
                print(f"  ℹ️  View {view} does not exist yet")

        except Exception as e:
            print(f"  ⚠️  Failed to refresh {view}: {str(e)[:200]}")
            conn.rollback()

    cursor.close()


def get_database_stats(conn):
    """Get database statistics"""
    print("\n📊 Database Statistics:")

    cursor = conn.cursor()

    # Table sizes
    cursor.execute("""
        SELECT
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        LIMIT 10
    """)

    print("\n  Top 10 Largest Tables:")
    for row in cursor.fetchall():
        print(f"    {row[1]}: {row[2]}")

    # Index count
    cursor.execute("""
        SELECT COUNT(*) as index_count
        FROM pg_indexes
        WHERE schemaname = 'public'
    """)
    index_count = cursor.fetchone()[0]
    print(f"\n  Total Indexes: {index_count}")

    # Materialized view count
    cursor.execute("""
        SELECT COUNT(*) as view_count
        FROM pg_matviews
        WHERE schemaname = 'public'
    """)
    view_count = cursor.fetchone()[0]
    print(f"  Materialized Views: {view_count}")

    # Materialized view sizes
    cursor.execute("""
        SELECT
            matviewname,
            pg_size_pretty(pg_total_relation_size('public.'||matviewname)) as size
        FROM pg_matviews
        WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size('public.'||matviewname) DESC
    """)

    if cursor.rowcount > 0:
        print("\n  Materialized View Sizes:")
        for row in cursor.fetchall():
            print(f"    {row[0]}: {row[1]}")

    cursor.close()


def verify_optimizations(conn):
    """Verify that optimizations were applied"""
    print("\n✅ Verifying Optimizations:")

    cursor = conn.cursor()

    # Check materialized views
    expected_views = [
        'top_scorers',
        'match_results_summary',
        'player_season_stats',
        'quiz_global_leaderboard',
        'recent_matches',
        'player_career_highlights',
    ]

    print("\n  Materialized Views:")
    for view in expected_views:
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = %s)",
            (view,)
        )
        exists = cursor.fetchone()[0]
        status = "✅" if exists else "❌"
        print(f"    {status} {view}")

    # Check indexes
    expected_indexes = [
        'idx_quiz_rounds_game_round',
        'idx_quiz_answers_round_player',
        'idx_quiz_questions_category_used',
        'idx_quiz_games_status_created',
        'idx_chat_messages_metadata',
        'idx_quiz_questions_metadata',
    ]

    print("\n  New Indexes:")
    for index in expected_indexes:
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = %s)",
            (index,)
        )
        exists = cursor.fetchone()[0]
        status = "✅" if exists else "❌"
        print(f"    {status} {index}")

    # Check functions
    expected_functions = [
        'refresh_all_materialized_views',
        'refresh_quiz_views',
        'refresh_football_views',
    ]

    print("\n  Refresh Functions:")
    for func in expected_functions:
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = %s)",
            (func,)
        )
        exists = cursor.fetchone()[0]
        status = "✅" if exists else "❌"
        print(f"    {status} {func}()")

    cursor.close()


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Apply performance optimizations to Neon database')
    parser.add_argument('--db-url', help='Database URL (or use DATABASE_URL env var)')
    parser.add_argument('--skip-refresh', action='store_true', help='Skip refreshing materialized views')
    parser.add_argument('--stats-only', action='store_true', help='Only show database statistics')

    args = parser.parse_args()

    db_url = args.db_url or get_database_url()

    print("=" * 80)
    print("🚀 Performance Optimization Script")
    print("=" * 80)

    # Connect to database
    conn = connect_to_database(db_url)

    if args.stats_only:
        get_database_stats(conn)
        conn.close()
        return

    try:
        # Apply optimizations
        migration_file = 'database/migrations/003_performance_optimizations.sql'
        execute_sql_file(conn, migration_file)

        # Refresh materialized views
        if not args.skip_refresh:
            refresh_materialized_views(conn)
        else:
            print("\nℹ️  Skipping materialized view refresh (--skip-refresh)")

        # Verify optimizations
        verify_optimizations(conn)

        # Show statistics
        get_database_stats(conn)

        print("\n" + "=" * 80)
        print("✅ Performance optimizations applied successfully!")
        print("=" * 80)
        print("\nNext Steps:")
        print("  1. Monitor query performance improvements")
        print("  2. Set up automated refresh schedule:")
        print("     - Use pg_cron (if available on Neon)")
        print("     - Or create a scheduled task to call refresh functions")
        print("  3. Proceed to Phase 2: Redis caching implementation")
        print("\nManual Refresh Commands:")
        print("  SELECT refresh_all_materialized_views();")
        print("  SELECT refresh_quiz_views();")
        print("  SELECT refresh_football_views();")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        conn.close()
        print("\n👋 Database connection closed")


if __name__ == '__main__':
    main()
