#!/usr/bin/env python3
"""
Manual corrections for player name mismatches between lineups and profiles
"""
import sqlite3
from pathlib import Path
from bs4 import BeautifulSoup
import re

# Manual mapping: DB name -> profile filename (without .html)
NAME_CORRECTIONS = {
    "Hönnscheidt": "hoennscheid",  # Spelling variant: dt vs d
    # Add more as needed
}

def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())

def apply_manual_corrections(db_path: str, base_path: str = "fsvarchiv"):
    """Apply manual corrections for known name mismatches"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('='*80)
    print('MANUELLE SPIELER-KORREKTUREN')
    print('='*80)
    
    spieler_dir = Path(base_path) / "spieler"
    corrected = 0
    
    for db_name, profile_filename in NAME_CORRECTIONS.items():
        print(f'\nKorrigiere: "{db_name}" -> "{profile_filename}.html"')
        
        # Finde Spieler in DB
        cursor.execute('''
            SELECT player_id, name
            FROM players
            WHERE name = ? OR name LIKE ?
        ''', (db_name, f'%{db_name}%'))
        
        players = cursor.fetchall()
        
        if not players:
            print(f'  ✗ Spieler "{db_name}" nicht in DB gefunden')
            continue
        
        # Lade Profil
        profile_path = spieler_dir / f"{profile_filename}.html"
        
        if not profile_path.exists():
            print(f'  ✗ Profil-Datei nicht gefunden: {profile_path}')
            continue
        
        with profile_path.open('r', encoding='latin-1', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'lxml')
        
        # Parse Profil-Daten
        information = soup.get_text("\n", strip=True)
        
        # Parse birth date
        from datetime import datetime
        birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n]+)", information, re.DOTALL)
        birth_date = None
        birth_place = None
        if birth_match:
            try:
                birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                birth_date = birth_match.group(1)
            birth_place = birth_match.group(2).strip()
        
        # Parse height and weight
        height_match = re.search(r"(\d{2,3})\s*cm", information)
        height_cm = int(height_match.group(1)) if height_match else None
        
        weight_match = re.search(r"(\d{2,3})\s*kg", information)
        weight_kg = int(weight_match.group(1)) if weight_match else None
        
        # Parse position
        primary_position = None
        position_header = soup.find("b", string=re.compile("Position", re.IGNORECASE))
        if position_header:
            parent = position_header.find_parent()
            if parent:
                found_header = False
                for string in parent.stripped_strings:
                    if found_header and string and not string.endswith(":"):
                        primary_position = normalize_whitespace(string)
                        break
                    if "position" in string.lower():
                        found_header = True
        
        # Parse nationality
        nationality = None
        nationality_header = soup.find("b", string=re.compile(r"Nationalit[aä]t", re.IGNORECASE))
        if nationality_header:
            parent = nationality_header.find_parent()
            if parent:
                found_header = False
                for string in parent.stripped_strings:
                    if found_header and string and not string.endswith(":"):
                        nationality = normalize_whitespace(string)
                        break
                    if "nationalit" in string.lower():
                        found_header = True
        
        # Update alle gefundenen Spieler
        for pid, name in players:
            cursor.execute('''
                UPDATE players
                SET birth_date = COALESCE(?, birth_date),
                    birth_place = COALESCE(?, birth_place),
                    height_cm = COALESCE(?, height_cm),
                    weight_kg = COALESCE(?, weight_kg),
                    primary_position = COALESCE(?, primary_position),
                    nationality = COALESCE(?, nationality),
                    profile_url = COALESCE(?, profile_url)
                WHERE player_id = ?
            ''', (birth_date, birth_place, height_cm, weight_kg, primary_position, 
                  nationality, f"spieler/{profile_filename}.html", pid))
            
            print(f'  ✓ Aktualisiert ID {pid}: "{name}"')
            print(f'     Nat: {nationality}, Pos: {primary_position}, Größe: {height_cm}')
            corrected += 1
    
    conn.commit()
    conn.close()
    
    print(f'\n{"="*80}')
    print(f'✓ {corrected} Spieler manuell korrigiert')
    print('='*80)

if __name__ == '__main__':
    apply_manual_corrections('fsv_archive_complete.db')

