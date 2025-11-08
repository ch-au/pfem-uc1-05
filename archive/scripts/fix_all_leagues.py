#!/usr/bin/env python3
"""
Vollständige Liga-Korrektur basierend auf HTML-Quelldaten.

Liest ALLE Saisonen aus den HTML-Dateien und aktualisiert die Datenbank
mit den korrekten Liga-Bezeichnungen.
"""

import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def extract_all_leagues(archive_path: Path):
    """Extrahiert Liga-Bezeichnungen aus allen HTML-Dateien."""
    
    season_dirs = sorted([d for d in archive_path.iterdir() 
                         if d.is_dir() and re.match(r'\d{4}-\d{2}', d.name)])
    
    season_leagues = {}
    
    for season_dir in season_dirs:
        season_label = season_dir.name
        
        for filename in ['profiliga.html', 'profitab.html', 'profitabb.html']:
            html_file = season_dir / filename
            if html_file.exists():
                try:
                    with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                        soup = BeautifulSoup(f, 'lxml')
                    
                    title = soup.find('b')
                    if title:
                        title_text = title.get_text(strip=True)
                        
                        # Extrahiere Liga nach Doppelpunkt
                        if ':' in title_text:
                            league = title_text.split(':')[1].strip()
                            season_leagues[season_label] = league
                except Exception as e:
                    print(f"Fehler bei {season_label}: {e}")
                
                break
    
    return season_leagues


def determine_league_level(league_name: str) -> str:
    """Bestimmt die Liga-Ebene basierend auf dem Namen."""
    
    lower = league_name.lower()
    
    # 1. Bundesliga (ohne "2.")
    if 'bundesliga' in lower and '2.' not in lower and 'süd' not in lower:
        return 'first_division'
    
    # 2. Bundesliga
    if '2. bundesliga' in lower or '2.bundesliga' in lower:
        return 'second_division'
    
    # 3. Liga / Regionalliga  
    if 'regionalliga' in lower:
        return 'third_division'
    
    # Amateur/Oberliga
    if any(x in lower for x in ['amateur', 'oberliga', 'amateurliga']):
        return 'amateur'
    
    # Historische Ligen
    if any(x in lower for x in ['gauliga', 'bezirks', 'kreis', 'klasse']):
        return 'historical'
    
    # Default
    return 'other'


def update_all_competitions(season_leagues: dict):
    """Aktualisiert alle Wettbewerbe und Saisonen in der Datenbank."""
    
    conn = psycopg2.connect(os.getenv('DB_URL'))
    
    print('Erstelle/aktualisiere alle Wettbewerbe...')
    print()
    
    # Sammle alle einzigartigen Ligen
    unique_leagues = set(season_leagues.values())
    
    with conn.cursor() as cur:
        for league in sorted(unique_leagues):
            level = determine_league_level(league)
            norm_name = league.lower()
            
            cur.execute('''
                INSERT INTO public.competitions (name, normalized_name, level)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE 
                SET level = EXCLUDED.level
            ''', (league, norm_name, level))
            
            print(f'  ✓ {league:50s} ({level})')
        
        conn.commit()
    
    print()
    print(f'Insgesamt {len(unique_leagues)} Wettbewerbe verarbeitet')
    print()
    
    # Aktualisiere season_competitions
    print('Aktualisiere Saison-Zuordnungen...')
    print()
    
    updates = 0
    
    with conn.cursor() as cur:
        # Hole alle competition IDs
        cur.execute('SELECT competition_id, name FROM public.competitions')
        comp_ids = {name: cid for cid, name in cur.fetchall()}
        
        for season_label, league_name in season_leagues.items():
            # Hole season_id
            cur.execute('SELECT season_id FROM public.seasons WHERE label = %s', (season_label,))
            result = cur.fetchone()
            if not result:
                continue
            
            season_id = result[0]
            new_comp_id = comp_ids.get(league_name)
            
            if not new_comp_id:
                continue
            
            # Update oder insert season_competition
            cur.execute('''
                INSERT INTO public.season_competitions (season_id, competition_id)
                VALUES (%s, %s)
                ON CONFLICT (season_id, competition_id) DO NOTHING
            ''', (season_id, new_comp_id))
            
            # Falls es eine alte Zuordnung gibt (zu \"Bundesliga\"), update sie
            cur.execute('''
                UPDATE public.season_competitions sc
                SET competition_id = %s
                FROM public.competitions c
                WHERE sc.season_competition_id IN (
                    SELECT sc2.season_competition_id
                    FROM public.season_competitions sc2
                    JOIN public.competitions c2 ON sc2.competition_id = c2.competition_id
                    WHERE sc2.season_id = %s
                    AND c2.name NOT IN (SELECT name FROM public.competitions WHERE competition_id = %s)
                    AND c2.name NOT IN ('DFB-Pokal', 'Europapokal')
                )
            ''', (new_comp_id, season_id, new_comp_id))
            
            if cur.rowcount > 0:
                updates += 1
    
    conn.commit()
    conn.close()
    
    print(f'✓ {updates} Saisonen aktualisiert')
    
    return updates


def main():
    """Hauptprogramm."""
    print('=' * 80)
    print('VOLLSTÄNDIGE LIGA-KORREKTUR')
    print('=' * 80)
    print()
    
    archive_path = Path('fsvarchiv')
    season_leagues = extract_all_leagues(archive_path)
    
    print()
    print('=' * 80)
    print()
    
    updates = update_all_competitions(season_leagues)
    
    print()
    print('=' * 80)
    print('✅ ALLE LIGEN KORRIGIERT')
    print('=' * 80)
    print(f'{updates} Saisonen aktualisiert')
    print(f'{len(season_leagues)} Saisonen insgesamt klassifiziert')


if __name__ == '__main__':
    main()
