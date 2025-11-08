#!/usr/bin/env python3
"""
Fix and clean teams table
"""
import sqlite3

def fix_teams_table(db_path: str):
    """Fix team names and clean teams table"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('='*100)
    print('TEAMS-TABELLE BEREINIGUNG')
    print('='*100)
    
    # 1. Prüfe "FSV" Team
    print('\n1. Korrigiere Haupt-FSV-Team...')
    
    cursor.execute('SELECT team_id, name, normalized_name FROM teams WHERE team_id = 36')
    team = cursor.fetchone()
    
    if team:
        tid, name, norm = team
        print(f'   Aktuell: ID {tid} = "{name}"')
        
        # Korrigiere zu vollem Namen
        cursor.execute('''
            UPDATE teams
            SET name = '1. FSV Mainz 05',
                normalized_name = '1 fsv mainz 05'
            WHERE team_id = 36
        ''')
        print(f'   ✓ Korrigiert zu: "1. FSV Mainz 05"')
    
    # 2. Prüfe ob es jetzt Konflikte gibt
    print('\n2. Prüfe auf Namenskonflikte...')
    
    cursor.execute('''
        SELECT name, COUNT(*) as count
        FROM teams
        GROUP BY name
        HAVING COUNT(*) > 1
    ''')
    
    konflikte = cursor.fetchall()
    if konflikte:
        print(f'   ⚠ Gefunden: {len(konflikte)} Konflikte')
        for name, count in konflikte:
            print(f'     "{name}": {count}x')
    else:
        print('   ✓ Keine Namenskonflikte')
    
    # 3. Konsolidiere FSV-Teams (falls gewünscht)
    print('\n3. FSV Mainz 05 Varianten:')
    print('-'*100)
    
    cursor.execute('''
        SELECT 
            t.team_id,
            t.name,
            COUNT(DISTINCT m.match_id) as spiele,
            MIN(m.match_date) as von,
            MAX(m.match_date) as bis
        FROM teams t
        LEFT JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
        WHERE t.name LIKE '%Mainz%' AND (t.name LIKE '%05%' OR t.name LIKE '%FSV%')
        GROUP BY t.team_id, t.name
        ORDER BY MIN(m.match_date)
    ''')
    
    header = '   {:<5} {:<45} {:<8} {:<12} {:<12}'.format('ID', 'Name', 'Spiele', 'Von', 'Bis')
    print(header)
    print('   ' + '-'*95)
    
    for tid, name, spiele, von, bis in cursor.fetchall():
        von_str = str(von) if von else '-'
        bis_str = str(bis) if bis else '-'
        row = '   {:<5} {:<45} {:<8} {:<12} {:<12}'.format(tid, name, spiele, von_str, bis_str)
        print(row)
    
    # 4. Prüfe sehr kurze Namen (potenzielle Fehler)
    print('\n4. Korrigiere sehr kurze Team-Namen...')
    
    cursor.execute('''
        SELECT team_id, name
        FROM teams
        WHERE LENGTH(name) <= 5
        AND team_id != 36  -- Bereits korrigiert
    ''')
    
    kurze_namen = cursor.fetchall()
    if kurze_namen:
        print(f'   Gefunden: {len(kurze_namen)} Teams mit sehr kurzen Namen')
        for tid, name in kurze_namen:
            print(f'     ID {tid}: \"{name}\"')
    else:
        print('   ✓ Keine problematischen kurzen Namen')
    
    conn.commit()
    
    # 5. Finale Statistik
    print('\n' + '='*100)
    print('BEREINIGUNG ABGESCHLOSSEN')
    print('='*100)
    
    cursor.execute('SELECT COUNT(*) FROM teams')
    total = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(*)
        FROM teams t
        JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
    ''')
    mit_spielen = cursor.fetchone()[0]
    
    print(f'\nTeams gesamt: {total}')
    print(f'Teams mit Spielen: {mit_spielen}')
    print(f'\n✓ Haupt-FSV-Team korrigiert: "FSV" → "1. FSV Mainz 05"')
    
    conn.close()

if __name__ == '__main__':
    fix_teams_table('fsv_archive_complete.db')

