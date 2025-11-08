#!/usr/bin/env python3
"""
Script zum Vergleich der Datenqualität vor und nach Re-Parse.
"""

#!/usr/bin/env python3
"""
Script zum Vergleich der Datenqualität vor und nach Re-Parse.
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
spec = importlib.util.spec_from_file_location("test_data_quality", Path(__file__).parent / "test_data_quality.py")
test_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_module)
DataQualityTester = test_module.DataQualityTester


def compare_results(before_file: str, after_file: str):
    """Vergleiche Test-Ergebnisse vor und nach Re-Parse."""
    
    print("=" * 80)
    print("VERGLEICH: VORHER vs. NACHHER")
    print("=" * 80)
    
    # Lade vorherige Ergebnisse
    before_results = {}
    if Path(before_file).exists():
        with open(before_file, 'r') as f:
            before_content = f.read()
            # Extrahiere Zahlen
            import re
            before_results['matches'] = int(re.search(r'Gesamt Spiele: (\d+)', before_content).group(1)) if re.search(r'Gesamt Spiele: (\d+)', before_content) else 0
            before_results['players'] = int(re.search(r'Gesamt Spieler: ([\d,]+)', before_content).replace(',', '')) if re.search(r'Gesamt Spieler: ([\d,]+)', before_content) else 0
            before_results['mainz_matches'] = int(re.search(r'Gesamt Spiele \(FSV Mainz\): ([\d,]+)', before_content).replace(',', '')) if re.search(r'Gesamt Spiele \(FSV Mainz\): ([\d,]+)', before_content) else 0
            before_results['mainz_teams'] = int(re.search(r'Mainz-Teams: (\d+)', before_content).group(1)) if re.search(r'Mainz-Teams: (\d+)', before_content) else 0
            before_results['problematic_players'] = int(re.search(r'(\d+) Spieler mit Sonderzeichen', before_content).group(1)) if re.search(r'(\d+) Spieler mit Sonderzeichen', before_content) else 0
    
    # Teste aktuelle Datenbank
    tester = DataQualityTester('sqlite', 'fsv_archive_complete.db')
    try:
        tester.connect()
        results = tester.run_all_tests()
    finally:
        tester.close()
    
    # Vergleich
    print("\n" + "=" * 80)
    print("VERGLEICHS-TABELLE")
    print("=" * 80)
    print(f"{'Metrik':<40} {'Vorher':<15} {'Nachher':<15} {'Änderung':<15}")
    print("-" * 80)
    
    if before_results:
        matches_change = results.get('season_coverage', {}).get('total_matches', 0) - before_results.get('matches', 0)
        print(f"{'Gesamt Spiele':<40} {before_results.get('matches', 0):<15,} {results.get('season_coverage', {}).get('total_matches', 0):<15,} {matches_change:+,}")
        
        players_change = results.get('player_statistics', {}).get('total_players', 0) - before_results.get('players', 0)
        print(f"{'Gesamt Spieler':<40} {before_results.get('players', 0):<15,} {results.get('player_statistics', {}).get('total_players', 0):<15,} {players_change:+,}")
        
        mainz_matches_change = results.get('match_results', {}).get('total_matches', 0) - before_results.get('mainz_matches', 0)
        print(f"{'Mainz Spiele':<40} {before_results.get('mainz_matches', 0):<15,} {results.get('match_results', {}).get('total_matches', 0):<15,} {mainz_matches_change:+,}")
        
        mainz_teams_change = results.get('team_consistency', {}).get('mainz_teams', 0) - before_results.get('mainz_teams', 0)
        print(f"{'Mainz-Team-Varianten':<40} {before_results.get('mainz_teams', 0):<15,} {results.get('team_consistency', {}).get('mainz_teams', 0):<15,} {mainz_teams_change:+,}")
        
        problematic_change = results.get('player_consistency', {}).get('special_chars', 0) - before_results.get('problematic_players', 0)
        print(f"{'Spieler mit Sonderzeichen':<40} {before_results.get('problematic_players', 0):<15,} {results.get('player_consistency', {}).get('special_chars', 0):<15,} {problematic_change:+,}")
    
    print("\n" + "=" * 80)
    print("VERBESSERUNGEN")
    print("=" * 80)
    
    if results.get('team_consistency', {}).get('mainz_teams', 0) == 1:
        print("✅ Team-Konsolidierung: Nur noch 1 Mainz-Team!")
    else:
        print(f"⚠️  Team-Konsolidierung: {results.get('team_consistency', {}).get('mainz_teams', 0)} Varianten gefunden")
    
    if results.get('player_consistency', {}).get('special_chars', 0) == 0:
        print("✅ Spielernamen: Keine Sonderzeichen mehr!")
    else:
        print(f"⚠️  Spielernamen: {results.get('player_consistency', {}).get('special_chars', 0)} mit Sonderzeichen")


if __name__ == '__main__':
    compare_results('test_results_before.txt', 'test_results_after.txt')

