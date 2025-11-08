#!/usr/bin/env python3
"""
Korrigiert die Liga-Klassifikation basierend auf den Original-HTML-Dateien.

Liest aus den HTML-Dateien die korrekte Liga (1. Bundesliga, 2. Bundesliga, etc.)
und aktualisiert die Datenbank entsprechend.

Usage:
    python fix_league_classification.py --dry-run
    python fix_league_classification.py
"""

import argparse
import os
import re
from pathlib import Path
from typing import Dict, Optional
from bs4 import BeautifulSoup
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def extract_league_from_html(season_dir: Path) -> Optional[str]:
    """Extrahiert Liga-Bezeichnung aus HTML-Datei."""
    
    # Suche profiliga.html oder profitab.html
    for filename in ['profiliga.html', 'profitab.html', 'profitabb.html']:
        html_file = season_dir / filename
        if html_file.exists():
            try:
                with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f, 'lxml')
                
                # Hole den kompletten Text
                text = soup.get_text()
                
                # Suche im Title/Header
                title = soup.find('b') or soup.find('title')
                if title:
                    title_text = title.get_text()
                    
                    # Prüfe auf 2. Bundesliga
                    if '2. Bundesliga' in title_text or '2.Bundesliga' in title_text:
                        return '2. Bundesliga'
                    
                    # Prüfe auf andere Ligen
                    if 'Gauliga' in title_text:
                        # Extrahiere genaue Gauliga-Bezeichnung
                        match = re.search(r'Gauliga[^<\n]*', title_text)
                        return match.group(0).strip() if match else 'Gauliga'
                    
                    if 'Bezirksliga' in title_text:
                        match = re.search(r'Bezirksliga[^<\n]*', title_text)
                        return match.group(0).strip() if match else 'Bezirksliga'
                    
                    if 'Kreisliga' in title_text:
                        match = re.search(r'Kreisliga[^<\n]*', title_text)
                        return match.group(0).strip() if match else 'Kreisliga'
                    
                    # Wenn nur "Bundesliga" ohne "2." → 1. Bundesliga
                    if 'Bundesliga' in title_text:
                        return 'Bundesliga'
                
                # Fallback: Suche im gesamten Text
                if '2. Bundesliga' in text:
                    return '2. Bundesliga'
                
                return None
                
            except Exception as e:
                print(f"  Fehler beim Lesen von {html_file}: {e}")
                return None
    
    return None


def scan_all_seasons(archive_path: Path) -> Dict[str, str]:
    """Scannt alle Saisonen und identifiziert die Liga."""
    
    print("Scanne alle Saisonen...")
    print()
    
    season_leagues = {}
    
    # Alle Saison-Verzeichnisse
    season_dirs = [d for d in archive_path.iterdir() 
                   if d.is_dir() and re.match(r'\d{4}-\d{2}', d.name)]
    
    season_dirs.sort()
    
    for season_dir in season_dirs:
        season_label = season_dir.name
        league = extract_league_from_html(season_dir)
        
        if league:
            season_leagues[season_label] = league
            
            # Zeige nur interessante Fälle
            if league == '2. Bundesliga' or '2004' in season_label or '2005' in season_label:
                print(f"  {season_label}: {league}")
    
    print()
    print(f"Insgesamt {len(season_leagues)} Saisonen klassifiziert")
    
    return season_leagues


def update_database(season_leagues: Dict[str, str], dry_run: bool = False):
    """Aktualisiert die Datenbank mit korrekten Liga-Zuordnungen."""
    
    print()
    print("=" * 80)
    print("DATENBANK-UPDATE")
    print("=" * 80)
    print()
    
    conn = psycopg2.connect(os.getenv("DB_URL"))
    
    # 1. Erstelle "2. Bundesliga" Wettbewerb falls nicht vorhanden
    print("1. Erstelle fehlende Wettbewerbe...")
    
    with conn.cursor() as cur:
        # Prüfe welche Wettbewerbe existieren
        cur.execute("SELECT name FROM public.competitions")
        existing_comps = {row[0] for row in cur.fetchall()}
        
        # Sammle alle benötigten Wettbewerbe
        needed_comps = set(season_leagues.values())
        missing_comps = needed_comps - existing_comps
        
        if missing_comps:
            print(f"   Fehlende Wettbewerbe: {missing_comps}")
            
            for comp in sorted(missing_comps):
                if dry_run:
                    print(f"   [DRY RUN] Würde erstellen: {comp}")
                else:
                    # Bestimme Level
                    if '2. Bundesliga' in comp:
                        level = 'second_division'
                    elif 'Bundesliga' in comp and '2.' not in comp:
                        level = 'first_division'
                    elif 'Gauliga' in comp or 'Bezirksliga' in comp or 'Kreisliga' in comp:
                        level = 'regional'
                    else:
                        level = 'league'
                    
                    cur.execute('''
                        INSERT INTO public.competitions (name, normalized_name, level)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (name) DO NOTHING
                    ''', (comp, comp.lower(), level))
                    
                    print(f"   ✓ Erstellt: {comp} (Level: {level})")
            
            if not dry_run:
                conn.commit()
        else:
            print("   Alle benötigten Wettbewerbe existieren bereits")
    
    # 2. Aktualisiere season_competitions
    print()
    print("2. Aktualisiere Saison-Wettbewerb-Zuordnungen...")
    
    updates_needed = 0
    updates_applied = 0
    
    with conn.cursor() as cur:
        # Hole alle competition IDs
        cur.execute("SELECT competition_id, name FROM public.competitions")
        comp_ids = {name: comp_id for comp_id, name in cur.fetchall()}
        
        for season_label, league_name in season_leagues.items():
            # Hole season_id
            cur.execute("SELECT season_id FROM public.seasons WHERE label = %s", (season_label,))
            result = cur.fetchone()
            
            if not result:
                continue
            
            season_id = result[0]
            
            # Prüfe aktuelle Zuordnung
            cur.execute('''
                SELECT c.name, sc.season_competition_id
                FROM public.season_competitions sc
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                WHERE sc.season_id = %s
                AND c.name IN ('Bundesliga', '2. Bundesliga')
            ''', (season_id,))
            
            current = cur.fetchone()
            
            if current:
                current_league, sc_id = current
                
                # Muss aktualisiert werden?
                if current_league != league_name:
                    updates_needed += 1
                    
                    if dry_run:
                        print(f"   [DRY RUN] {season_label}: {current_league} → {league_name}")
                    else:
                        new_comp_id = comp_ids.get(league_name)
                        if new_comp_id:
                            # Update season_competition
                            cur.execute('''
                                UPDATE public.season_competitions
                                SET competition_id = %s
                                WHERE season_competition_id = %s
                            ''', (new_comp_id, sc_id))
                            
                            updates_applied += 1
                            print(f"   ✓ {season_label}: {current_league} → {league_name}")
    
    if not dry_run and updates_applied > 0:
        conn.commit()
    
    print()
    print(f"   Aktualisierungen: {updates_applied}/{updates_needed}")
    
    conn.close()
    
    return updates_applied


def main():
    parser = argparse.ArgumentParser(description='Korrigiere Liga-Klassifikation')
    parser.add_argument('--dry-run', action='store_true', help='Zeige nur was geändert würde')
    args = parser.parse_args()
    
    print('=' * 80)
    print('LIGA-KLASSIFIKATION KORREKTUR')
    print('=' * 80)
    if args.dry_run:
        print('MODE: DRY RUN')
    else:
        print('MODE: LIVE')
    print()
    
    archive_path = Path('fsvarchiv')
    
    if not archive_path.exists():
        print(f'❌ Archiv-Verzeichnis nicht gefunden: {archive_path}')
        return
    
    # Scanne Saisonen
    season_leagues = scan_all_seasons(archive_path)
    
    # Aktualisiere Datenbank
    updates = update_database(season_leagues, dry_run=args.dry_run)
    
    print()
    print('=' * 80)
    if args.dry_run:
        print('DRY RUN ABGESCHLOSSEN')
    else:
        print('✅ LIGA-KLASSIFIKATION KORRIGIERT')
        print(f'   {updates} Saisonen aktualisiert')
    print('=' * 80)


if __name__ == '__main__':
    main()

