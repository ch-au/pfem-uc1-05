#!/usr/bin/env python3
"""
Test script for comprehensive_fsv_parser.py
Tests batch operations and validation with a small season.
"""

import sys
import logging
import time
from pathlib import Path
from parsing.comprehensive_fsv_parser import ComprehensiveFSVParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def test_parser(test_season: str = None):
    """Test parser with optional season filter."""
    print("=" * 80)
    print("FSV Parser Test - Batch Operations & Validation")
    print("=" * 80)
    
    # Use test database
    db_name = "fsv_archive_test.db"
    
    # Remove existing test database if it exists
    if Path(db_name).exists():
        print(f"Removing existing test database: {db_name}")
        Path(db_name).unlink()
    
    parser = ComprehensiveFSVParser(
        base_path="fsvarchiv",
        db_name=db_name,
        seasons=[test_season] if test_season else None
    )
    
    print(f"\nStarting parser...")
    print(f"  Archive path: {parser.base_path}")
    print(f"  Database: {db_name}")
    print(f"  Season filter: {test_season if test_season else 'ALL'}")
    
    start_time = time.time()
    
    try:
        parser.run()
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 80)
        print("TEST RESULTS")
        print("=" * 80)
        print(f"✓ Parsing completed successfully in {elapsed:.2f} seconds")
        print(f"✓ Average time per match: {elapsed / max(parser.stats['matches_processed'], 1):.3f} seconds")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n✗ Error during parsing: {e}")
        print(f"  Time elapsed: {elapsed:.2f} seconds")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test FSV parser with batch operations")
    parser.add_argument(
        "--season",
        help="Test with specific season (e.g., 2023-24)",
        default=None
    )
    
    args = parser.parse_args()
    
    success = test_parser(args.season)
    sys.exit(0 if success else 1)

