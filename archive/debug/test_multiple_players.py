#!/usr/bin/env python3
"""
Test multiple player profiles to ensure parsing works correctly
"""
import sqlite3
from pathlib import Path
from comprehensive_fsv_parser import ComprehensiveFSVParser, normalize_name

def test_multiple_players():
    """Test parsing of multiple player profiles"""
    
    test_db = "test_multiple_players.db"
    
    # Remove old test database if it exists
    if Path(test_db).exists():
        Path(test_db).unlink()
    
    # Create parser
    parser = ComprehensiveFSVParser(
        base_path="fsvarchiv",
        db_name=test_db
    )
    
    season_path = Path("fsvarchiv/2014-15")
    
    # Test players - mix of modern and older entries
    test_players = [
        ("Brosinski", 178, 70, "deutsch", "Verteidiger"),
        ("Hack", None, None, None, None),  # May not have all data
        ("Bell", None, None, None, None),  # May not have all data
    ]
    
    print("="*80)
    print("TESTING MULTIPLE PLAYER PROFILES")
    print("="*80)
    
    results = []
    
    for player_name, expected_height, expected_weight, expected_nat, expected_pos in test_players:
        print(f"\nTesting: {player_name}")
        print("-"*40)
        
        # Parse player profile
        parser.parse_player_profile(player_name, season_path)
        
        # Query results
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        
        normalized = normalize_name(player_name)
        cursor.execute("""
            SELECT name, height_cm, weight_kg, nationality, primary_position
            FROM players
            WHERE normalized_name LIKE ?
        """, (f"%{normalized}%",))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            name, height, weight, nationality, position = row
            print(f"  Name: {name}")
            print(f"  Height: {height} cm" if height else "  Height: Not found")
            print(f"  Weight: {weight} kg" if weight else "  Weight: Not found")
            print(f"  Nationality: {nationality}" if nationality else "  Nationality: Not found")
            print(f"  Position: {position}" if position else "  Position: Not found")
            
            # Check expectations
            if expected_height and height != expected_height:
                print(f"  ✗ Expected height {expected_height}, got {height}")
                results.append(False)
            elif expected_weight and weight != expected_weight:
                print(f"  ✗ Expected weight {expected_weight}, got {weight}")
                results.append(False)
            elif expected_nat and (not nationality or expected_nat.lower() not in nationality.lower()):
                print(f"  ✗ Expected nationality '{expected_nat}', got '{nationality}'")
                results.append(False)
            elif expected_pos and (not position or expected_pos.lower() not in position.lower()):
                print(f"  ✗ Expected position '{expected_pos}', got '{position}'")
                results.append(False)
            else:
                print(f"  ✓ All expected fields match!")
                results.append(True)
        else:
            print(f"  ✗ Player not found in database")
            results.append(False)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if all(results):
        print("\n✓ ALL TESTS PASSED!")
    else:
        print("\n✗ Some tests failed")
    
    print(f"\nTest database: {test_db}")

if __name__ == "__main__":
    test_multiple_players()

