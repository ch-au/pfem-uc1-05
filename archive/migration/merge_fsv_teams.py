#!/usr/bin/env python3
"""
Merge duplicate FSV teams: migrate Team 1 into Team 36, then rename Team 36
"""
import sqlite3

def merge_fsv_teams(db_path: str):
    """Merge Team 1 (10 games) into Team 36 (2996 games) and fix name"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('='*100)
    print('FSV TEAMS ZUSAMMENFÜHRUNG')
    print('='*100)
    
    # 1. Migriere alle Referenzen von Team 1 → Team 36
    print('\n1. Migriere Spiele von Team 1 → Team 36...')
    
    # Heimspiele
    cursor.execute('UPDATE matches SET home_team_id = 36 WHERE home_team_id = 1')
    home_updated = cursor.rowcount
    print(f'   ✓ {home_updated} Heimspiele migriert')
    
    # Auswärtsspiele
    cursor.execute('UPDATE matches SET away_team_id = 36 WHERE away_team_id = 1')
    away_updated = cursor.rowcount
    print(f'   ✓ {away_updated} Auswärtsspiele migriert')
    
    # Match lineups
    cursor.execute('UPDATE match_lineups SET team_id = 36 WHERE team_id = 1')
    lineups_updated = cursor.rowcount
    print(f'   ✓ {lineups_updated} Lineup-Einträge migriert')
    
    # Substitutions
    cursor.execute('UPDATE match_substitutions SET team_id = 36 WHERE team_id = 1')
    subs_updated = cursor.rowcount
    print(f'   ✓ {subs_updated} Substitution-Einträge migriert')
    
    # Goals
    cursor.execute('UPDATE goals SET team_id = 36 WHERE team_id = 1')
    goals_updated = cursor.rowcount
    print(f'   ✓ {goals_updated} Tor-Einträge migriert')
    
    # Cards
    cursor.execute('UPDATE cards SET team_id = 36 WHERE team_id = 1')
    cards_updated = cursor.rowcount
    print(f'   ✓ {cards_updated} Karten-Einträge migriert')
    
    # Match coaches
    cursor.execute('UPDATE match_coaches SET team_id = 36 WHERE team_id = 1')
    coaches_updated = cursor.rowcount
    print(f'   ✓ {coaches_updated} Coach-Einträge migriert')
    
    # Seasons
    cursor.execute('UPDATE seasons SET team_id = 36 WHERE team_id = 1')
    seasons_updated = cursor.rowcount
    print(f'   ✓ {seasons_updated} Saison-Einträge migriert')
    
    # 2. Lösche Team 1
    print('\n2. Lösche Team 1...')
    cursor.execute('DELETE FROM teams WHERE team_id = 1')
    print(f'   ✓ Team 1 gelöscht')
    
    # 3. Benenne Team 36 um
    print('\n3. Benenne Team 36 um...')
    cursor.execute('''
        UPDATE teams
        SET name = '1. FSV Mainz 05',
            normalized_name = '1 fsv mainz 05'
        WHERE team_id = 36
    ''')
    print(f'   ✓ Team 36: "FSV" → "1. FSV Mainz 05"')
    
    conn.commit()
    
    # 4. Verifizierung
    print('\n' + '='*100)
    print('VERIFIZIERUNG')
    print('='*100)
    
    cursor.execute('''
        SELECT 
            t.team_id,
            t.name,
            COUNT(m.match_id) as spiele
        FROM teams t
        LEFT JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
        WHERE t.name LIKE '%Mainz%' AND (t.name LIKE '%05%' OR t.name LIKE '%FSV%')
        GROUP BY t.team_id, t.name
        ORDER BY spiele DESC
    ''')
    
    print('\nFSV Teams nach Zusammenführung:')
    for tid, name, spiele in cursor.fetchall():
        marker = ' *** HAUPT-TEAM ***' if tid == 36 else ''
        print(f'  ID {tid:>3}: {name:<45} {spiele:>5} Spiele{marker}')
    
    print('\n✓ Zusammenführung erfolgreich!')
    print(f'  Gesamt migriert: {home_updated + away_updated} Spiele')
    
    conn.close()

if __name__ == '__main__':
    merge_fsv_teams('fsv_archive_complete.db')

