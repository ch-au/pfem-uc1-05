#!/usr/bin/env python3
"""
Script zur Bereinigung von Spielernamen mit "?" am Anfang.

Entfernt "?" Präfixe von Spielernamen in der Datenbank.
"""

import sys
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import Config
import psycopg2


def clean_player_names(db_type='sqlite', db_path='fsv_archive_complete.db', dry_run=True):
    """Bereinige Spielernamen mit '?' am Anfang."""
    
    if db_type == 'sqlite':
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
    else:
        config = Config()
        conn = psycopg2.connect(config.build_psycopg2_dsn())
        cur = conn.cursor()
    
    print("=" * 80)
    print(f"{'DRY RUN - ' if dry_run else ''}SPIELERNAMEN-BEREINIGUNG")
    print("=" * 80)
    
    # Finde Spieler mit "?" am Anfang
    if db_type == 'sqlite':
        cur.execute("""
            SELECT player_id, name FROM players
            WHERE name LIKE '?%'
            ORDER BY player_id
        """)
    else:
        cur.execute("""
            SELECT player_id, name FROM public.players
            WHERE name LIKE '?%'
            ORDER BY player_id
        """)
    
    players_to_fix = cur.fetchall()
    
    print(f"\nGefunden: {len(players_to_fix)} Spieler mit '?' am Anfang")
    
    if not players_to_fix:
        print("✓ Keine Spieler zum Bereinigen gefunden")
        conn.close()
        return
    
    # Zeige erste 10
    print("\nErste 10 Beispiele:")
    for player_id, name in players_to_fix[:10]:
        cleaned = name[1:].strip() if name.startswith('?') else name
        print(f"  {player_id}: '{name}' → '{cleaned}'")
    
    if dry_run:
        print(f"\n⚠️  DRY RUN - Keine Änderungen vorgenommen!")
        print(f"   Verwende --execute um Bereinigung durchzuführen.")
    else:
        print(f"\nBereinige {len(players_to_fix)} Spieler...")
        
        updated = 0
        for player_id, name in players_to_fix:
            cleaned = name[1:].strip() if name.startswith('?') else name
            
            if not cleaned or cleaned == "-":
                print(f"  ⚠️  Überspringe {player_id}: '{name}' (wird zu leer)")
                continue
            
            if db_type == 'sqlite':
                cur.execute("""
                    UPDATE players
                    SET name = ?, normalized_name = LOWER(REPLACE(REPLACE(REPLACE(name, '.', ' '), '-', ' '), ' ', ''))
                    WHERE player_id = ?
                """, (cleaned, player_id))
            else:
                cur.execute("""
                    UPDATE public.players
                    SET name = %s
                    WHERE player_id = %s
                """, (cleaned, player_id))
            
            updated += 1
        
        conn.commit()
        print(f"\n✓ {updated} Spieler bereinigt")
    
    conn.close()


def main():
    """Hauptfunktion."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bereinige Spielernamen mit "?" am Anfang')
    parser.add_argument('--db-type', choices=['sqlite', 'postgres'], default='sqlite',
                       help='Datenbank-Typ')
    parser.add_argument('--db-path', default='fsv_archive_complete.db',
                       help='Pfad zur SQLite-Datenbank')
    parser.add_argument('--execute', action='store_true',
                       help='Führe Bereinigung tatsächlich aus')
    
    args = parser.parse_args()
    
    clean_player_names(args.db_type, args.db_path, dry_run=not args.execute)


if __name__ == '__main__':
    main()

