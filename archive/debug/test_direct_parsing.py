#!/usr/bin/env python3
"""
Test direct player profile parsing
"""
import sqlite3
from pathlib import Path
from comprehensive_fsv_parser import ComprehensiveFSVParser

def test_direct_parsing():
    """Test parsing player profile directly"""
    
    # Create a test database
    test_db = "test_direct_parsing.db"
    
    # Remove old test database if it exists
    if Path(test_db).exists():
        Path(test_db).unlink()
    
    # Create parser
    parser = ComprehensiveFSVParser(
        base_path="fsvarchiv",
        db_name=test_db
    )
    
    print("Testing direct player profile parsing...")
    print("="*80)
    
    # Manually call parse_player_profile
    season_path = Path("fsvarchiv/2014-15")
    
    # First, check if the player file exists in the index
    print("\nPlayer file index:")
    for name, path in list(parser.player_file_index.items())[:5]:
        print(f"  {name}: {path}")
    
    # Check if brosinski is in the index
    from comprehensive_fsv_parser import normalize_name
    normalized_name = normalize_name("Brosinski")
    print(f"\nNormalized name for 'Brosinski': '{normalized_name}'")
    
    if normalized_name in parser.player_file_index:
        print(f"✓ Found in index: {parser.player_file_index[normalized_name]}")
    else:
        print("✗ Not found in index")
        print(f"\nAll indexed names containing 'bro':")
        for name in parser.player_file_index.keys():
            if 'bro' in name:
                print(f"  - {name}")
    
    # Try to parse the player profile directly
    print("\nCalling parse_player_profile...")
    parser.parse_player_profile("Brosinski", season_path)
    
    # Check the results
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, height_cm, weight_kg, nationality, primary_position, birth_date, birth_place
        FROM players
        WHERE normalized_name LIKE '%brosinski%'
    """)
    
    results = cursor.fetchall()
    
    print("\n" + "="*80)
    print("RESULTS:")
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
            
            # Verify
            if height == 178 and weight == 70 and nationality and position:
                print("\n✓ SUCCESS! All fields parsed correctly!")
            else:
                print("\n✗ Some fields missing or incorrect")
    else:
        print("No results found")
        
        print("\nAll players in database:")
        cursor.execute("SELECT name, normalized_name FROM players LIMIT 20")
        for row in cursor.fetchall():
            print(f"  - {row[0]} (normalized: {row[1]})")
    
    conn.close()
    print(f"\nTest database: {test_db}")

if __name__ == "__main__":
    test_direct_parsing()

