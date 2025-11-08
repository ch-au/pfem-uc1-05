#!/usr/bin/env python3
"""
Clean and validate player data in the database
"""
import sqlite3
import re
from pathlib import Path

def clean_player_data(db_path: str):
    """Clean invalid player entries from database"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('='*80)
    print('SPIELER-DATENBEREINIGUNG')
    print('='*80)
    
    # 1. Identifiziere ungültige Spieler
    invalid_patterns = [
        (r'^\d+$', 'Nur Zahlen'),
        (r'^-+$', 'Nur Bindestriche'),
        (r'^\d+\.\s+\d+:\d+', 'Tor-Zeit-Format'),
        (r'^(FE|HE|ET|EL),\s', 'Tor-Beschreibung (FE/HE/ET)'),
        (r',\s+.+\s+an\s+', 'Assist-Beschreibung'),
        (r'^\(.*\)$', 'Nur Klammern'),
    ]
    
    to_delete = set()
    
    print('\nIdentifiziere ungültige Einträge:')
    print('-'*80)
    
    cursor.execute('SELECT player_id, name FROM players')
    all_players = cursor.fetchall()
    
    for pid, name in all_players:
        for pattern, description in invalid_patterns:
            if re.match(pattern, name):
                to_delete.add(pid)
                print(f'  ID {pid}: "{name}" - {description}')
                break
    
    print(f'\nGefunden: {len(to_delete)} ungültige Spieler-Einträge')
    
    if to_delete:
        # Prüfe ob diese Spieler in anderen Tabellen referenziert werden
        cursor.execute(f'''
            SELECT COUNT(*)
            FROM match_lineups
            WHERE player_id IN ({','.join('?' * len(to_delete))})
        ''', list(to_delete))
        lineup_refs = cursor.fetchone()[0]
        
        cursor.execute(f'''
            SELECT COUNT(*)
            FROM goals
            WHERE player_id IN ({','.join('?' * len(to_delete))})
            OR assist_player_id IN ({','.join('?' * len(to_delete))})
        ''', list(to_delete) * 2)
        goal_refs = cursor.fetchone()[0]
        
        print(f'\nReferenzen:')
        print(f'  In match_lineups: {lineup_refs}')
        print(f'  In goals: {goal_refs}')
        
        if lineup_refs > 0 or goal_refs > 0:
            print('\n⚠ WARNUNG: Diese Spieler werden in anderen Tabellen referenziert!')
            print('  Empfehlung: Manuell prüfen oder mit NULL ersetzen')
            
            # Zeige Beispiele
            print('\nBeispiele aus match_lineups:')
            cursor.execute(f'''
                SELECT l.lineup_id, p.name, m.source_file
                FROM match_lineups l
                JOIN players p ON l.player_id = p.player_id
                JOIN matches m ON l.match_id = m.match_id
                WHERE l.player_id IN ({','.join('?' * min(5, len(to_delete)))})
                LIMIT 5
            ''', list(to_delete)[:5])
            
            for lid, name, source in cursor.fetchall():
                print(f'    Lineup {lid}: "{name}" in {source}')
        else:
            print('\n✓ Keine Referenzen gefunden - sicher zu löschen')
    
    # 2. Identifiziere Spieler ohne Profil-Daten aber mit Einsätzen
    cursor.execute('''
        SELECT 
            p.player_id,
            p.name,
            COUNT(DISTINCT ml.match_id) as appearances,
            p.nationality,
            p.height_cm
        FROM players p
        JOIN match_lineups ml ON p.player_id = ml.player_id
        WHERE p.nationality IS NULL
        AND p.height_cm IS NULL
        GROUP BY p.player_id, p.name, p.nationality, p.height_cm
        HAVING COUNT(DISTINCT ml.match_id) >= 5
        ORDER BY appearances DESC
        LIMIT 20
    ''')
    
    print('\n' + '='*80)
    print('SPIELER MIT VIELEN EINSÄTZEN ABER OHNE PROFIL-DATEN:')
    print('='*80)
    
    missing_profile_data = cursor.fetchall()
    for pid, name, apps, nat, height in missing_profile_data:
        print(f'  ID {pid:>5}: "{name:<30}" - {apps:>3} Einsätze, Profil: {"FEHLT" if not nat and not height else "OK"}')
    
    # 3. Statistik über Namens-Varianten
    cursor.execute('''
        SELECT 
            normalized_name,
            COUNT(*) as variants,
            GROUP_CONCAT(name, ' | ') as names
        FROM players
        GROUP BY normalized_name
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 10
    ''')
    
    print('\n' + '='*80)
    print('SPIELER MIT MEHREREN NAMENS-VARIANTEN:')
    print('='*80)
    
    for norm_name, count, names in cursor.fetchall():
        # Truncate if too long
        names_display = names if len(names) < 100 else names[:97] + '...'
        print(f'  "{norm_name}" ({count} Varianten): {names_display}')
    
    conn.close()
    
    print('\n' + '='*80)
    print('ZUSAMMENFASSUNG:')
    print('='*80)
    print(f'  • {len(to_delete)} ungültige Einträge gefunden')
    print(f'  • {len(missing_profile_data)} häufige Spieler ohne Profil-Daten')
    print(f'  • Nur {100*has_nat/total:.1f}% der Spieler haben vollständige Profile')

if __name__ == '__main__':
    clean_player_data('fsv_archive_complete.db')

