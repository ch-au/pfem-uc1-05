#!/usr/bin/env python3
"""
Test script to verify player parsing improvements
"""
import sqlite3
from pathlib import Path
from comprehensive_fsv_parser import ComprehensiveFSVParser

def test_player_parsing():
    """Test if player attributes are being parsed correctly"""
    
    # Create a test database
    test_db = "test_player_parsing.db"
    
    # Remove old test database if it exists
    if Path(test_db).exists():
        Path(test_db).unlink()
    
    # Create parser with just one season that contains Brosinski
    parser = ComprehensiveFSVParser(
        base_path="fsvarchiv",
        db_name=test_db,
        seasons=["2014-15"]  # Brosinski's first season with Mainz
    )
    
    print("Parsing season 2014-15...")
    parser.parse_season("2014-15")
    
    # Check the results
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    # Query for Brosinski
    cursor.execute("""
        SELECT name, height_cm, weight_kg, nationality, primary_position, birth_date, birth_place
        FROM players
        WHERE name LIKE '%Brosinski%' OR name LIKE '%BROSINSKI%'
    """)
    
    results = cursor.fetchall()
    
    print("\n" + "="*80)
    print("RESULTS FOR BROSINSKI:")
    print("="*80)
    
    if results:
        for row in results:
            name, height, weight, nationality, position, birth_date, birth_place = row
            print(f"Name: {name}")
            print(f"Height: {height} cm" if height else "Height: Not found")
            print(f"Weight: {weight} kg" if weight else "Weight: Not found")
            print(f"Nationality: {nationality}" if nationality else "Nationality: Not found")
            print(f"Position: {position}" if position else "Position: Not found")
            print(f"Birth Date: {birth_date}" if birth_date else "Birth Date: Not found")
            print(f"Birth Place: {birth_place}" if birth_place else "Birth Place: Not found")
            print("-"*80)
            
            # Verify expected values (based on brosinski.html)
            assert height == 178, f"Expected height 178, got {height}"
            assert weight == 70, f"Expected weight 70, got {weight}"
            assert nationality and "deutsch" in nationality.lower(), f"Expected nationality 'deutsch', got {nationality}"
            assert position and "verteidiger" in position.lower(), f"Expected position 'Verteidiger', got {position}"
            
            print("\n✓ All assertions passed!")
    else:
        print("No results found for Brosinski")
        print("\nAll players in database:")
        cursor.execute("SELECT name FROM players LIMIT 10")
        for row in cursor.fetchall():
            print(f"  - {row[0]}")
    
    conn.close()
    
    print("\n" + "="*80)
    print("TEST COMPLETED")
    print("="*80)
    print(f"\nTest database saved as: {test_db}")
    print("You can inspect it with: sqlite3 test_player_parsing.db")

if __name__ == "__main__":
    test_player_parsing()

