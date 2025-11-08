#!/usr/bin/env python3
"""
Pre and post-migration validation for FSV Mainz 05 database.

Performs comprehensive data integrity checks before and after migrating
from SQLite to Postgres.

Usage:
    python validate_migration.py --mode pre --sqlite fsv_archive_complete.db
    python validate_migration.py --mode post --sqlite fsv_archive_complete.db --postgres "<dsn>"
"""

import argparse
import os
import sqlite3
import sys
from contextlib import closing
from typing import Dict, List, Tuple, Optional
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseValidator:
    """Validates database integrity for migration."""
    
    def __init__(self, sqlite_path: str, postgres_dsn: Optional[str] = None):
        self.sqlite_path = sqlite_path
        self.postgres_dsn = postgres_dsn
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        
    def log_error(self, msg: str):
        """Log an error."""
        self.errors.append(f"❌ ERROR: {msg}")
        
    def log_warning(self, msg: str):
        """Log a warning."""
        self.warnings.append(f"⚠️  WARNING: {msg}")
        
    def log_info(self, msg: str):
        """Log informational message."""
        self.info.append(f"ℹ️  INFO: {msg}")
    
    def validate_pre_migration(self) -> bool:
        """Run all pre-migration validation checks."""
        print("=" * 80)
        print("PRE-MIGRATION VALIDATION")
        print("=" * 80)
        print(f"SQLite Database: {self.sqlite_path}")
        print(f"Validation Time: {datetime.now().isoformat()}")
        print()
        
        with closing(sqlite3.connect(self.sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            
            # Run all validation checks
            self._check_row_counts(conn)
            self._check_null_constraints(conn)
            self._check_foreign_keys(conn)
            self._check_date_formats(conn)
            self._check_duplicates(conn)
            self._check_orphaned_records(conn)
            self._check_data_ranges(conn)
            
        # Print results
        self._print_results()
        
        return len(self.errors) == 0
    
    def validate_post_migration(self) -> bool:
        """Run post-migration validation checks."""
        print("=" * 80)
        print("POST-MIGRATION VALIDATION")
        print("=" * 80)
        print(f"SQLite Database: {self.sqlite_path}")
        print(f"Postgres DSN: {self.postgres_dsn}")
        print(f"Validation Time: {datetime.now().isoformat()}")
        print()
        
        with closing(sqlite3.connect(self.sqlite_path)) as sqlite_conn, \
             closing(psycopg2.connect(self.postgres_dsn)) as pg_conn:
            
            sqlite_conn.row_factory = sqlite3.Row
            
            # Compare row counts
            self._compare_row_counts(sqlite_conn, pg_conn)
            
            # Sample data validation
            self._validate_sample_data(sqlite_conn, pg_conn)
            
            # Check foreign key integrity
            self._check_postgres_foreign_keys(pg_conn)
            
            # Verify sequences
            self._check_sequences(pg_conn)
            
        # Print results
        self._print_results()
        
        return len(self.errors) == 0
    
    def _check_row_counts(self, conn: sqlite3.Connection):
        """Check row counts for all tables."""
        print("Checking row counts...")
        
        tables = [
            "teams", "competitions", "seasons", "season_competitions",
            "referees", "coaches", "players", "player_aliases", "player_careers",
            "season_squads", "matches", "match_coaches", "match_referees",
            "match_lineups", "match_substitutions", "goals", "cards",
            "match_notes", "season_matchdays"
        ]
        
        total_rows = 0
        for table in tables:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            total_rows += count
            self.log_info(f"Table '{table}': {count:,} rows")
            
            if count == 0 and table not in ["player_aliases", "match_notes"]:
                self.log_warning(f"Table '{table}' is empty")
        
        self.log_info(f"Total rows across all tables: {total_rows:,}")
        print()
    
    def _check_null_constraints(self, conn: sqlite3.Connection):
        """Check for NULL values in required fields."""
        print("Checking NULL constraints...")
        
        checks = [
            ("teams", "name"),
            ("teams", "normalized_name"),
            ("players", "name"),
            ("players", "normalized_name"),
            ("coaches", "name"),
            ("referees", "name"),
            ("competitions", "name"),
            ("seasons", "label"),
        ]
        
        for table, column in checks:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL OR {column} = ''")
            count = cur.fetchone()[0]
            if count > 0:
                self.log_error(f"Table '{table}' has {count} NULL/empty values in '{column}'")
            else:
                self.log_info(f"Table '{table}.{column}': No NULL values ✓")
        print()
    
    def _check_foreign_keys(self, conn: sqlite3.Connection):
        """Check foreign key integrity."""
        print("Checking foreign key integrity...")
        
        # Enable foreign key checking
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Check for foreign key violations
        cur = conn.execute("PRAGMA foreign_key_check")
        violations = cur.fetchall()
        
        if violations:
            for violation in violations:
                self.log_error(f"Foreign key violation: {violation}")
        else:
            self.log_info("No foreign key violations ✓")
        print()
    
    def _check_date_formats(self, conn: sqlite3.Connection):
        """Validate date formats."""
        print("Checking date formats...")
        
        # Check match dates
        cur = conn.execute("""
            SELECT match_id, match_date 
            FROM matches 
            WHERE match_date IS NOT NULL 
            AND match_date NOT LIKE '____-__-__'
            LIMIT 10
        """)
        invalid_dates = cur.fetchall()
        
        if invalid_dates:
            self.log_error(f"Found {len(invalid_dates)} invalid match dates")
            for row in invalid_dates[:5]:
                self.log_error(f"  Match {row[0]}: '{row[1]}'")
        else:
            self.log_info("All match dates in valid YYYY-MM-DD format ✓")
        
        # Check player birth dates
        cur = conn.execute("""
            SELECT player_id, name, birth_date 
            FROM players 
            WHERE birth_date IS NOT NULL 
            AND birth_date NOT LIKE '____-__-__'
            LIMIT 10
        """)
        invalid_birth = cur.fetchall()
        
        if invalid_birth:
            self.log_warning(f"Found {len(invalid_birth)} invalid birth dates")
            for row in invalid_birth[:5]:
                self.log_warning(f"  Player {row[1]}: '{row[2]}'")
        else:
            self.log_info("All birth dates in valid format ✓")
        print()
    
    def _check_duplicates(self, conn: sqlite3.Connection):
        """Check for duplicate records in unique columns."""
        print("Checking for duplicates...")
        
        checks = [
            ("teams", "name"),
            ("teams", "normalized_name"),
            ("players", "name"),
            ("coaches", "name"),
            ("referees", "name"),
            ("seasons", "label"),
        ]
        
        for table, column in checks:
            cur = conn.execute(f"""
                SELECT {column}, COUNT(*) as cnt 
                FROM {table} 
                WHERE {column} IS NOT NULL
                GROUP BY {column} 
                HAVING cnt > 1
            """)
            duplicates = cur.fetchall()
            
            if duplicates:
                self.log_error(f"Table '{table}' has {len(duplicates)} duplicate values in '{column}'")
                for dup in duplicates[:3]:
                    self.log_error(f"  '{dup[0]}' appears {dup[1]} times")
            else:
                self.log_info(f"No duplicates in '{table}.{column}' ✓")
        print()
    
    def _check_orphaned_records(self, conn: sqlite3.Connection):
        """Check for orphaned records (foreign key references to non-existent records)."""
        print("Checking for orphaned records...")
        
        checks = [
            ("matches", "season_competition_id", "season_competitions", "season_competition_id"),
            ("matches", "home_team_id", "teams", "team_id"),
            ("matches", "away_team_id", "teams", "team_id"),
            ("goals", "match_id", "matches", "match_id"),
            ("goals", "player_id", "players", "player_id"),
            ("match_lineups", "match_id", "matches", "match_id"),
            ("match_lineups", "player_id", "players", "player_id"),
        ]
        
        for child_table, child_col, parent_table, parent_col in checks:
            cur = conn.execute(f"""
                SELECT COUNT(*) 
                FROM {child_table} 
                WHERE {child_col} IS NOT NULL 
                AND {child_col} NOT IN (SELECT {parent_col} FROM {parent_table})
            """)
            count = cur.fetchone()[0]
            
            if count > 0:
                self.log_error(f"Table '{child_table}' has {count} orphaned records in '{child_col}'")
            else:
                self.log_info(f"No orphaned records in '{child_table}.{child_col}' ✓")
        print()
    
    def _check_data_ranges(self, conn: sqlite3.Connection):
        """Check data ranges for reasonableness."""
        print("Checking data ranges...")
        
        # Check season years
        cur = conn.execute("SELECT MIN(start_year), MAX(end_year) FROM seasons")
        min_year, max_year = cur.fetchone()
        if min_year and max_year:
            self.log_info(f"Season range: {min_year} - {max_year}")
            if min_year < 1900 or max_year > 2030:
                self.log_warning(f"Unusual season year range: {min_year} - {max_year}")
        
        # Check match scores
        cur = conn.execute("SELECT MAX(home_score), MAX(away_score) FROM matches")
        max_home, max_away = cur.fetchone()
        if max_home and max_home > 15:
            self.log_warning(f"Unusually high home score found: {max_home}")
        if max_away and max_away > 15:
            self.log_warning(f"Unusually high away score found: {max_away}")
        
        # Check player heights
        cur = conn.execute("SELECT MIN(height_cm), MAX(height_cm) FROM players WHERE height_cm IS NOT NULL")
        min_height, max_height = cur.fetchone()
        if min_height and min_height < 150:
            self.log_warning(f"Unusually short player height: {min_height}cm")
        if max_height and max_height > 220:
            self.log_warning(f"Unusually tall player height: {max_height}cm")
        
        self.log_info("Data range checks complete")
        print()
    
    def _compare_row_counts(self, sqlite_conn: sqlite3.Connection, pg_conn):
        """Compare row counts between SQLite and Postgres."""
        print("Comparing row counts...")
        
        tables = [
            "teams", "competitions", "seasons", "season_competitions",
            "referees", "coaches", "players", "player_aliases", "player_careers",
            "season_squads", "matches", "match_coaches", "match_referees",
            "match_lineups", "match_substitutions", "goals", "cards",
            "match_notes", "season_matchdays"
        ]
        
        all_match = True
        for table in tables:
            sqlite_cur = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cur.fetchone()[0]
            
            with pg_conn.cursor() as pg_cur:
                pg_cur.execute(f"SELECT COUNT(*) FROM public.{table}")
                pg_count = pg_cur.fetchone()[0]
            
            if sqlite_count != pg_count:
                self.log_error(f"Row count mismatch in '{table}': SQLite={sqlite_count}, Postgres={pg_count}")
                all_match = False
            else:
                self.log_info(f"Table '{table}': {sqlite_count:,} rows (match) ✓")
        
        if all_match:
            self.log_info("All row counts match! ✓")
        print()
    
    def _validate_sample_data(self, sqlite_conn: sqlite3.Connection, pg_conn):
        """Validate sample data matches between databases."""
        print("Validating sample data...")
        
        # Sample a few records from key tables
        checks = [
            ("teams", "team_id", ["name", "normalized_name"]),
            ("players", "player_id", ["name", "normalized_name"]),
            ("matches", "match_id", ["match_date", "home_score", "away_score"]),
            ("goals", "goal_id", ["minute", "score_home", "score_away"]),
        ]
        
        for table, id_col, columns in checks:
            # Get a sample ID
            sqlite_cur = sqlite_conn.execute(f"SELECT {id_col} FROM {table} LIMIT 1")
            row = sqlite_cur.fetchone()
            if not row:
                continue
            
            sample_id = row[0]
            
            # Get data from both databases
            col_list = ", ".join(columns)
            sqlite_cur = sqlite_conn.execute(f"SELECT {col_list} FROM {table} WHERE {id_col} = ?", (sample_id,))
            sqlite_data = sqlite_cur.fetchone()
            
            with pg_conn.cursor() as pg_cur:
                pg_cur.execute(f"SELECT {col_list} FROM public.{table} WHERE {id_col} = %s", (sample_id,))
                pg_data = pg_cur.fetchone()
            
            if sqlite_data and pg_data:
                # Convert to tuples for comparison
                sqlite_tuple = tuple(sqlite_data)
                pg_tuple = tuple(str(x) if x is not None else None for x in pg_data)
                sqlite_tuple_str = tuple(str(x) if x is not None else None for x in sqlite_tuple)
                
                if sqlite_tuple_str == pg_tuple:
                    self.log_info(f"Sample data matches in '{table}' ✓")
                else:
                    self.log_error(f"Sample data mismatch in '{table}' (ID={sample_id})")
                    self.log_error(f"  SQLite: {sqlite_tuple}")
                    self.log_error(f"  Postgres: {pg_tuple}")
            elif not sqlite_data and not pg_data:
                self.log_info(f"No data in '{table}' to compare")
            else:
                self.log_error(f"Data exists in one database but not the other for '{table}'")
        print()
    
    def _check_postgres_foreign_keys(self, pg_conn):
        """Check that all foreign keys are properly set up in Postgres."""
        print("Checking Postgres foreign keys...")
        
        with pg_conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    tc.table_name, 
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                ORDER BY tc.table_name, kcu.column_name
            """)
            
            fk_count = 0
            for row in cur.fetchall():
                fk_count += 1
            
            if fk_count > 0:
                self.log_info(f"Found {fk_count} foreign key constraints in Postgres ✓")
            else:
                self.log_error("No foreign key constraints found in Postgres!")
        print()
    
    def _check_sequences(self, pg_conn):
        """Check that sequences are properly set after migration."""
        print("Checking Postgres sequences...")
        
        tables = [
            ("teams", "team_id"),
            ("competitions", "competition_id"),
            ("seasons", "season_id"),
            ("players", "player_id"),
            ("matches", "match_id"),
        ]
        
        for table, column in tables:
            with pg_conn.cursor() as cur:
                # Get max ID in table
                cur.execute(f"SELECT MAX({column}) FROM public.{table}")
                max_id = cur.fetchone()[0]
                
                # Get current sequence value
                cur.execute(f"SELECT last_value FROM public.{table}_{column}_seq")
                seq_value = cur.fetchone()[0]
                
                if max_id and seq_value:
                    if seq_value > max_id:
                        self.log_info(f"Sequence for '{table}.{column}': OK (max={max_id}, seq={seq_value}) ✓")
                    else:
                        self.log_error(f"Sequence for '{table}.{column}' is too low (max={max_id}, seq={seq_value})")
        print()
    
    def _print_results(self):
        """Print validation results."""
        print("\n" + "=" * 80)
        print("VALIDATION RESULTS")
        print("=" * 80)
        
        if self.info:
            print(f"\n✅ {len(self.info)} checks passed:")
            for msg in self.info[:10]:  # Show first 10
                print(f"  {msg}")
            if len(self.info) > 10:
                print(f"  ... and {len(self.info) - 10} more")
        
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warnings:")
            for msg in self.warnings:
                print(f"  {msg}")
        
        if self.errors:
            print(f"\n❌ {len(self.errors)} errors found:")
            for msg in self.errors:
                print(f"  {msg}")
            print("\n⚠️  MIGRATION SHOULD NOT PROCEED WITH ERRORS!")
        else:
            print("\n✅ No errors found - database is ready for migration!")
        
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Validate FSV Mainz 05 database migration")
    parser.add_argument("--mode", choices=["pre", "post"], required=True,
                       help="Validation mode: 'pre' before migration, 'post' after migration")
    parser.add_argument("--sqlite", default="fsv_archive_complete.db",
                       help="Path to SQLite database")
    parser.add_argument("--postgres", help="Postgres DSN (or use DB_URL in .env)")
    
    args = parser.parse_args()
    
    # Get Postgres DSN from args or environment
    postgres_dsn = args.postgres or os.getenv("DB_URL")
    
    if args.mode == "post" and not postgres_dsn:
        print("Error: Postgres DSN not provided!")
        print("  Either pass --postgres argument or set DB_URL in .env file")
        sys.exit(1)
    
    validator = DatabaseValidator(args.sqlite, postgres_dsn)
    
    if args.mode == "pre":
        success = validator.validate_pre_migration()
    else:
        success = validator.validate_post_migration()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

