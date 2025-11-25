#!/usr/bin/env python3
"""
Check PostgreSQL sync status
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from config import Config

def main():
    config = Config()
    
    if not config.PG_ENABLED:
        print("❌ PostgreSQL is not enabled")
        print("   Set DB_URL environment variable")
        return
    
    try:
        import psycopg2
        
        # Get connection
        dsn = config.build_psycopg2_dsn()
        print(f"🔌 Connecting to PostgreSQL...")
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        # Check if matches table exists
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        print(f"\n✅ Connected successfully!")
        print(f"📋 Found {len(tables)} tables in public schema\n")
        
        # Check core tables
        core_tables = ['teams', 'players', 'coaches', 'matches', 'goals', 'cards']
        
        for table in core_tables:
            if table in tables:
                cur.execute(f'SELECT COUNT(*) FROM {table}')
                count = cur.fetchone()[0]
                print(f"   ✓ {table:20s}: {count:>6,} records")
                
                # Additional checks
                if table == 'matches':
                    cur.execute("SELECT COUNT(*) FROM matches WHERE source_file LIKE '%profirest%'")
                    profirest = cur.fetchone()[0]
                    print(f"     → Profirest matches  : {profirest:>6,}")
                
                if table == 'players':
                    cur.execute("SELECT COUNT(*) FROM players WHERE name LIKE '% %'")
                    full_names = cur.fetchone()[0]
                    print(f"     → With full names    : {full_names:>6,}")
                
                if table == 'coaches':
                    cur.execute("SELECT COUNT(*) FROM coaches WHERE name LIKE '% %'")
                    full_names = cur.fetchone()[0]
                    print(f"     → With full names    : {full_names:>6,}")
            else:
                print(f"   ✗ {table:20s}: NOT FOUND")
        
        # Check quiz/chat tables
        print(f"\n📱 Application tables:")
        app_tables = ['quiz_games', 'quiz_questions', 'chat_sessions', 'chat_messages']
        for table in app_tables:
            if table in tables:
                cur.execute(f'SELECT COUNT(*) FROM {table}')
                count = cur.fetchone()[0]
                print(f"   ✓ {table:20s}: {count:>6,} records")
            else:
                print(f"   ✗ {table:20s}: NOT FOUND")
        
        # Check materialized views
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'MATERIALIZED VIEW'
            ORDER BY table_name
        """)
        views = [row[0] for row in cur.fetchall()]
        
        if views:
            print(f"\n📊 Materialized views:")
            for view in views:
                print(f"   ✓ {view}")
        
        # Now compare with SQLite
        print(f"\n" + "="*70)
        print("COMPARISON: SQLite vs PostgreSQL")
        print("="*70)
        
        import sqlite3
        sqlite_conn = sqlite3.connect('fsv_archive_complete.db')
        sqlite_cur = sqlite_conn.cursor()
        
        # Reopen PostgreSQL connection
        conn2 = psycopg2.connect(dsn)
        cur2 = conn2.cursor()
        
        for table in core_tables:
            if table in tables:  # Only compare if PG table exists
                sqlite_cur.execute(f'SELECT COUNT(*) FROM {table}')
                sqlite_count = sqlite_cur.fetchone()[0]
                
                cur2.execute(f'SELECT COUNT(*) FROM {table}')
                pg_count = cur2.fetchone()[0]
                
                diff = sqlite_count - pg_count
                status = "✅" if diff == 0 else "⚠️ "
                
                print(f"{status} {table:15s}: SQLite={sqlite_count:>6,}  PostgreSQL={pg_count:>6,}  Diff={diff:>6,}")
        
        sqlite_conn.close()
        conn.close()
        conn2.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

