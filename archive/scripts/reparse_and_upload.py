#!/usr/bin/env python3
"""
Script to backup SQLite DB and re-parse with improved parser, then upload to PostgreSQL.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from comprehensive_fsv_parser import ComprehensiveFSVParser

def backup_database(db_path: str) -> str:
    """Create a backup of the database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path

def main():
    sqlite_db = "fsv_archive_complete.db"
    
    print("=" * 80)
    print("FSV PARSER - FULL RE-PARSE & UPLOAD")
    print("=" * 80)
    
    # Step 1: Backup existing database
    if Path(sqlite_db).exists():
        print(f"\n1. Backing up existing database...")
        backup_path = backup_database(sqlite_db)
        print(f"   ✓ Backup created: {backup_path}")
    
    # Step 2: Remove old database
    print(f"\n2. Removing old database...")
    if Path(sqlite_db).exists():
        Path(sqlite_db).unlink()
        print(f"   ✓ Old database removed")
    
    # Step 3: Re-parse with improved parser
    print(f"\n3. Starting full re-parse with improved parser...")
    print(f"   This will take some time...")
    
    parser = ComprehensiveFSVParser(
        base_path="fsvarchiv",
        db_name=sqlite_db
    )
    
    try:
        parser.run()
        print(f"\n   ✓ Re-parse completed successfully!")
    except Exception as e:
        print(f"\n   ✗ Error during re-parse: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Upload to PostgreSQL
    print(f"\n4. Uploading to PostgreSQL...")
    try:
        # Get project root directory
        project_root = Path(__file__).parent.parent.parent
        upload_script = project_root / "upload_to_postgres.py"
        
        if not upload_script.exists():
            # Try archive/scripts directory
            upload_script = Path(__file__).parent.parent.parent / "archive" / "scripts" / "upload_to_postgres.py"
        
        if not upload_script.exists():
            print(f"\n   ⚠️  upload_to_postgres.py not found, skipping upload")
            print(f"   Please run manually: python upload_to_postgres.py --sqlite {sqlite_db}")
            return True
        
        result = subprocess.run(
            ["python3", str(upload_script), "--sqlite", sqlite_db],
            cwd=str(project_root),
            check=True,
            capture_output=False
        )
        print(f"\n   ✓ Upload completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n   ✗ Error during upload: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)
    print("All data has been:")
    print("  1. Re-parsed with improved parser (batch operations, validation)")
    print("  2. Uploaded to PostgreSQL")
    print("\nDatabase is now synchronized and up-to-date!")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

