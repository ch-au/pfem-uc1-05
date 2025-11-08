#!/usr/bin/env python3
"""
Comprehensive cleanup of player data
"""
import sqlite3
import re

def clean_database(db_path: str):
    """Clean invalid data from database"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('='*80)
    print('UMFASSENDE DATENBEREINIGUNG')
    print('='*80)
    
    # Define patterns for invalid player names
    invalid_patterns = [
        (r'^\d+$', 'Nur Zahlen (Trikot-Nummern)'),
        (r'^-+$', 'Nur Bindestriche'),
        (r'^\d+\.\s+\d+:\d+', 'Tor-Eintrag (z.B. "3. 0:1 ...")'),
        (r'^(FE|HE|ET|EL),\s', 'Tor-Beschreibung mit FE/HE/ET'),
        (r',\s+.+\s+an\s+', 'Assist-Beschreibung mit "an"'),
        (r'^\(.*\)$', 'Nur Klammern'),
        (r'dir\.\s*FS', 'Freistoß-Beschreibung'),
    ]
    
    print('\n1. Identifiziere ungültige Spieler-Einträge...')
    
    cursor.execute('SELECT player_id, name FROM players')
    all_players = cursor.fetchall()
    
    to_delete = set()
    categories = {}
    
    for pid, name in all_players:
        for pattern, category in invalid_patterns:
            if re.search(pattern, name):
                to_delete.add(pid)
                categories.setdefault(category, []).append((pid, name))
                break
    
    print(f'\nGefunden: {len(to_delete)} ungültige Einträge')
    for category, entries in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
        print(f'  - {len(entries):>4} {category}')
    
    # Strategy: Remove these from goals/assists tables, keep lineup if jersey numbers only
    print('\n2. Bereinige Tor-Tabelle...')
    
    cursor.execute(f'''
        DELETE FROM goals
        WHERE player_id IN ({','.join('?' * len(to_delete))})
        OR assist_player_id IN ({','.join('?' * len(to_delete))})
    ''', list(to_delete) * 2)
    
    goals_deleted = cursor.rowcount
    print(f'   ✓ {goals_deleted} Tor-Einträge entfernt')
    
    print('\n3. Bereinige Lineup-Tabelle (nur Tor-Zeitformat)...')
    
    # Only delete lineups for entries that are clearly goals (have ":" in name)
    to_delete_from_lineups = {pid for pid, name in all_players 
                              if pid in to_delete and ':' in name}
    
    if to_delete_from_lineups:
        cursor.execute(f'''
            DELETE FROM match_lineups
            WHERE player_id IN ({','.join('?' * len(to_delete_from_lineups))})
        ''', list(to_delete_from_lineups))
        
        lineups_deleted = cursor.rowcount
        print(f'   ✓ {lineups_deleted} Lineup-Einträge entfernt')
    
    print('\n4. Bereinige Substitutions-Tabelle...')
    
    cursor.execute(f'''
        DELETE FROM match_substitutions
        WHERE player_on_id IN ({','.join('?' * len(to_delete))})
        OR player_off_id IN ({','.join('?' * len(to_delete))})
    ''', list(to_delete) * 2)
    
    subs_deleted = cursor.rowcount
    print(f'   ✓ {subs_deleted} Substitution-Einträge entfernt')
    
    print('\n5. Lösche ungültige Spieler...')
    
    cursor.execute(f'''
        DELETE FROM players
        WHERE player_id IN ({','.join('?' * len(to_delete))})
    ''', list(to_delete))
    
    players_deleted = cursor.rowcount
    print(f'   ✓ {players_deleted} Spieler-Einträge entfernt')
    
    conn.commit()
    
    # Final statistics
    print('\n' + '='*80)
    print('BEREINIGUNG ABGESCHLOSSEN')
    print('='*80)
    
    cursor.execute('SELECT COUNT(*) FROM players')
    remaining_players = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM players WHERE nationality IS NOT NULL')
    with_nationality = cursor.fetchone()[0]
    
    print(f'\nVerbleibende Spieler: {remaining_players:,}')
    print(f'Mit Nationalität: {with_nationality:,} ({100*with_nationality/remaining_players:.1f}%)')
    
    print(f'\nEntfernt:')
    print(f'  - {players_deleted:,} Spieler')
    print(f'  - {goals_deleted:,} Tor-Einträge')
    print(f'  - {lineups_deleted:,} Lineup-Einträge')
    print(f'  - {subs_deleted:,} Substitution-Einträge')
    
    conn.close()
    return remaining_players

if __name__ == '__main__':
    clean_database('fsv_archive_complete.db')

