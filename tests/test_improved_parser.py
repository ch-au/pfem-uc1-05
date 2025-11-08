#!/usr/bin/env python3
"""
Test-Script für den verbesserten Parser.
Testet eine einzelne Saison und prüft ob Validierungen funktionieren.
"""

import sys
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsing.comprehensive_fsv_parser import ComprehensiveFSVParser
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

def test_parser_with_season(test_season: str = "2010-11"):
    """Teste Parser mit einer einzelnen Saison."""
    
    test_db = "fsv_archive_test.db"
    
    # Entferne alte Test-DB falls vorhanden
    if Path(test_db).exists():
        Path(test_db).unlink()
        print(f"✓ Alte Test-DB entfernt")
    
    print("=" * 80)
    print(f"TEST: Parser mit Saison {test_season}")
    print("=" * 80)
    
    # Erstelle Parser mit Test-Saison
    parser = ComprehensiveFSVParser(
        base_path="fsvarchiv",
        db_name=test_db,
        seasons=[test_season]
    )
    
    try:
        # Führe Parsing durch
        parser.run()
        
        print("\n" + "=" * 80)
        print("PARSING ABGESCHLOSSEN")
        print("=" * 80)
        
        # Zeige Statistiken
        stats = parser.stats
        print(f"\n📊 STATISTIKEN:")
        print(f"  Matches verarbeitet: {stats['matches_processed']}")
        print(f"  Matches erfolgreich: {stats['matches_successful']}")
        print(f"  Matches fehlgeschlagen: {stats['matches_failed']}")
        print(f"  Warnings: {len(stats['warnings'])}")
        print(f"  Errors: {len(stats['errors'])}")
        
        if stats['warnings']:
            print(f"\n⚠️  WARNINGS (erste 10):")
            for warning in stats['warnings'][:10]:
                print(f"    - {warning}")
        
        if stats['errors']:
            print(f"\n❌ ERRORS (erste 10):")
            for error in stats['errors'][:10]:
                print(f"    - {error}")
        
        # Prüfe Datenbank auf problematische Spieler-Namen
        print(f"\n🔍 PRÜFUNG: Problematische Spieler-Namen")
        conn = sqlite3.connect(test_db)
        cur = conn.cursor()
        
        # Prüfe auf Trainer-Namen
        cur.execute("""
            SELECT COUNT(*) FROM players 
            WHERE LOWER(name) LIKE '%trainer%' 
               OR LOWER(name) LIKE '%coach%'
               OR LOWER(name) LIKE '%fsv-trainer%'
        """)
        trainer_count = cur.fetchone()[0]
        
        # Prüfe auf Schiedsrichter-Namen
        cur.execute("""
            SELECT COUNT(*) FROM players 
            WHERE LOWER(name) LIKE '%schiedsrichter%'
        """)
        referee_count = cur.fetchone()[0]
        
        # Prüfe auf Tor-Text
        cur.execute("""
            SELECT COUNT(*) FROM players 
            WHERE LOWER(name) LIKE 'tore %'
               OR (name LIKE '%. %:%' AND name LIKE '%:%')
        """)
        goal_text_count = cur.fetchone()[0]
        
        # Prüfe auf Fehlertext-Präfixe
        cur.execute("""
            SELECT COUNT(*) FROM players 
            WHERE name LIKE 'FE,%' 
               OR name LIKE 'ET,%'
               OR name LIKE 'HE,%'
        """)
        error_prefix_count = cur.fetchone()[0]
        
        # Prüfe auf ungültige Patterns (beginnt nicht mit Buchstabe)
        # SQLite hat keine einfache Regex-Unterstützung, daher prüfen wir manuell
        cur.execute("SELECT name FROM players")
        all_names = cur.fetchall()
        invalid_pattern_count = 0
        for (name,) in all_names:
            if not name or len(name) < 2 or len(name) > 100:
                invalid_pattern_count += 1
            elif name[0] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÁÉÍÓÚÀÈÌÒÙÄËÏÖÜÂÊÎÔÛÇÑ':
                # Prüfe ob erster Buchstabe ein gültiger Buchstabe ist
                import unicodedata
                if not unicodedata.category(name[0]).startswith('L'):
                    invalid_pattern_count += 1
        
        # Gesamt-Spieler
        cur.execute("SELECT COUNT(*) FROM players")
        total_players = cur.fetchone()[0]
        
        print(f"  Gesamt Spieler: {total_players}")
        print(f"  Trainer-Namen: {trainer_count} {'❌' if trainer_count > 0 else '✓'}")
        print(f"  Schiedsrichter-Namen: {referee_count} {'❌' if referee_count > 0 else '✓'}")
        print(f"  Tor-Text: {goal_text_count} {'❌' if goal_text_count > 0 else '✓'}")
        print(f"  Fehlertext-Präfixe: {error_prefix_count} {'❌' if error_prefix_count > 0 else '✓'}")
        print(f"  Ungültige Patterns: {invalid_pattern_count} {'❌' if invalid_pattern_count > 0 else '✓'}")
        
        # Zeige problematische Namen falls vorhanden
        if trainer_count > 0:
            cur.execute("""
                SELECT name FROM players 
                WHERE LOWER(name) LIKE '%trainer%' 
                   OR LOWER(name) LIKE '%coach%'
                LIMIT 5
            """)
            print(f"\n  Beispiele Trainer-Namen:")
            for row in cur.fetchall():
                print(f"    - {row[0]}")
        
        if referee_count > 0:
            cur.execute("""
                SELECT name FROM players 
                WHERE LOWER(name) LIKE '%schiedsrichter%'
                LIMIT 5
            """)
            print(f"\n  Beispiele Schiedsrichter-Namen:")
            for row in cur.fetchall():
                print(f"    - {row[0]}")
        
        conn.close()
        
        # Bewertung
        print("\n" + "=" * 80)
        if trainer_count == 0 and referee_count == 0 and goal_text_count == 0 and error_prefix_count == 0:
            print("✅ TEST ERFOLGREICH: Keine problematischen Namen gefunden!")
        else:
            print("⚠️  TEST MIT WARNUNGEN: Einige problematische Namen gefunden")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ FEHLER während Parsing: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Teste verbesserten Parser')
    parser.add_argument('--season', default='2010-11', help='Saison zum Testen')
    
    args = parser.parse_args()
    
    success = test_parser_with_season(args.season)
    sys.exit(0 if success else 1)

