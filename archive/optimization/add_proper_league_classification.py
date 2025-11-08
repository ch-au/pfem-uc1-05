#!/usr/bin/env python3
"""
Add proper league classification based on year and Wikipedia history
"""
import sqlite3

def classify_league_by_year(year: int) -> str:
    """Classify league based on year and FSV Mainz 05 history"""
    
    # Basierend auf Wikipedia: https://de.wikipedia.org/wiki/1._FSV_Mainz_05
    
    if year >= 2004:
        return "Bundesliga"
    elif year >= 1997:
        return "2. Bundesliga"
    elif year >= 1989:
        return "Oberliga Südwest"  
    elif year >= 1978:
        return "2. Bundesliga Süd"
    elif year >= 1974:
        return "Regionalliga Südwest"
    elif year >= 1963:
        return "Amateurliga Südwest"
    elif year >= 1950:
        return "Oberliga Südwest"
    elif year >= 1945:
        return "Landesliga / Oberliga"
    elif year >= 1933:
        return "Gauliga Südwest"
    elif year >= 1923:
        return "Bezirksliga Hessen"
    elif year >= 1920:
        return "Kreisliga Hessen"
    elif year >= 1907:
        return "A-Klasse / B-Klasse"
    else:
        return "Regionalliga (früh)"

def update_league_classifications(db_path: str):
    """Update stage_label with proper league classification"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('='*100)
    print('LIGA-KLASSIFIZIERUNG KORREKTUR')
    print('='*100)
    
    # Hole alle season_competitions für "Bundesliga"
    cursor.execute('''
        SELECT 
            sc.season_competition_id,
            sc.stage_label,
            s.start_year,
            s.label
        FROM season_competitions sc
        JOIN seasons s ON sc.season_id = s.season_id
        JOIN competitions c ON sc.competition_id = c.competition_id
        WHERE c.name = 'Bundesliga'
        AND sc.stage_label = 'Bundesliga'
        ORDER BY s.start_year
    ''')
    
    season_comps = cursor.fetchall()
    print(f'\nGefunden: {len(season_comps)} Saison-Wettbewerbe mit stage_label=\"Bundesliga\"')
    
    # Update mit korrekter Klassifizierung
    updated = 0
    classifications = {}
    
    for sc_id, old_label, year, saison_label in season_comps:
        new_label = classify_league_by_year(year)
        
        if new_label != old_label:
            cursor.execute('''
                UPDATE season_competitions
                SET stage_label = ?
                WHERE season_competition_id = ?
            ''', (new_label, sc_id))
            updated += 1
            
            # Zähle Klassifizierungen
            classifications[new_label] = classifications.get(new_label, 0) + 1
    
    conn.commit()
    
    print(f'\n✓ {updated} season_competitions aktualisiert')
    
    print('\nNeue Liga-Klassifizierungen:')
    for liga, count in sorted(classifications.items(), key=lambda x: x[1], reverse=True):
        print(f'  {liga:<35} {count:>3} Saisonen')
    
    # Verifizierung
    print('\n' + '='*100)
    print('VERIFIZIERUNG:')
    print('='*100)
    
    cursor.execute('''
        SELECT DISTINCT 
            sc.stage_label,
            COUNT(*) as saisonen,
            MIN(s.start_year) as von,
            MAX(s.start_year) as bis
        FROM season_competitions sc
        JOIN seasons s ON sc.season_id = s.season_id
        JOIN competitions c ON sc.competition_id = c.competition_id
        WHERE c.name = 'Bundesliga'
        GROUP BY sc.stage_label
        ORDER BY von
    ''')
    
    print(f'\n{\"Liga\":<35} {\"Saisonen\":>10} {\"Von\":>8} {\"Bis\":>8}')
    print('-'*100)
    
    for liga, saisonen, von, bis in cursor.fetchall():
        print(f'{liga:<35} {saisonen:>10} {von:>8.0f} {bis:>8.0f}')
    
    conn.close()
    
    print('\n' + '='*100)
    print(f'✅ {updated} Ligen korrekt klassifiziert')
    print('='*100)

if __name__ == '__main__':
    update_league_classifications('fsv_archive_complete.db')

