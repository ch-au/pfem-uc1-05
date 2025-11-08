#!/usr/bin/env python3
"""
Smart player enrichment - match short names with full names
"""
import sqlite3
from pathlib import Path
from bs4 import BeautifulSoup
import re
import unicodedata
from datetime import datetime

def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())

def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))

def normalize_name(name: str) -> str:
    cleaned = strip_accents(name).replace(".", " ").replace("-", " ")
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", cleaned)
    return normalize_whitespace(cleaned).lower()

def extract_last_name(name: str) -> str:
    """Extract likely last name from full name"""
    parts = normalize_name(name).split()
    if parts:
        return parts[-1]  # Last word is usually the surname
    return ""

def read_html(path: Path):
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="latin-1", errors="ignore") as handle:
            return BeautifulSoup(handle.read(), "lxml")
    except OSError:
        return None

def enrich_players_smart(db_path: str, base_path: str = "fsvarchiv"):
    """Match and enrich players using smart name matching"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('='*80)
    print('INTELLIGENTES SPIELER-ENRICHMENT')
    print('='*80)
    
    # 1. Baue Index: last_name -> [player_ids with profile data]
    cursor.execute('''
        SELECT player_id, name, normalized_name
        FROM players
        WHERE nationality IS NOT NULL OR height_cm IS NOT NULL
    ''')
    
    profile_index = {}  # lastname -> [(player_id, full_name)]
    for pid, name, norm_name in cursor.fetchall():
        last_name = extract_last_name(name)
        if last_name:
            profile_index.setdefault(last_name, []).append((pid, name, norm_name))
    
    print(f'\n1. Index erstellt: {len(profile_index)} unterschiedliche Nachnamen mit Profil-Daten')
    
    # 2. Finde Spieler ohne Profil-Daten
    cursor.execute('''
        SELECT player_id, name, normalized_name
        FROM players
        WHERE nationality IS NULL AND height_cm IS NULL
        AND player_id IN (SELECT DISTINCT player_id FROM match_lineups)
    ''')
    
    players_without_profile = cursor.fetchall()
    print(f'2. Gefunden: {len(players_without_profile)} Spieler ohne Profil-Daten (aber mit Einsätzen)')
    
    # 3. Matche sie
    matches_found = 0
    enriched = 0
    
    print(f'\n3. Matching läuft...')
    
    for pid, name, norm_name in players_without_profile:
        # Extract last name from this player
        last_name = extract_last_name(name)
        
        if not last_name or last_name not in profile_index:
            continue
        
        # Found potential matches
        candidates = profile_index[last_name]
        
        if len(candidates) == 1:
            # Exact last name match with only one candidate - very likely correct
            source_pid, source_name, source_norm = candidates[0]
            
            # Copy data from source player
            cursor.execute('''
                UPDATE players
                SET 
                    birth_date = (SELECT birth_date FROM players WHERE player_id = ?),
                    birth_place = (SELECT birth_place FROM players WHERE player_id = ?),
                    height_cm = (SELECT height_cm FROM players WHERE player_id = ?),
                    weight_kg = (SELECT weight_kg FROM players WHERE player_id = ?),
                    primary_position = (SELECT primary_position FROM players WHERE player_id = ?),
                    nationality = (SELECT nationality FROM players WHERE player_id = ?),
                    image_url = (SELECT image_url FROM players WHERE player_id = ?),
                    profile_url = (SELECT profile_url FROM players WHERE player_id = ?)
                WHERE player_id = ?
            ''', (source_pid,) * 8 + (pid,))
            
            enriched += 1
            matches_found += 1
            
            if enriched <= 10:
                print(f'  ✓ "{name}" <- "{source_name}"')
        
        elif len(candidates) > 1:
            # Multiple candidates - try to match by checking if short name is contained
            for source_pid, source_name, source_norm in candidates:
                # Check if the short name matches the beginning or end of full name
                if norm_name in source_norm or source_norm.endswith(norm_name):
                    cursor.execute('''
                        UPDATE players
                        SET 
                            birth_date = (SELECT birth_date FROM players WHERE player_id = ?),
                            birth_place = (SELECT birth_place FROM players WHERE player_id = ?),
                            height_cm = (SELECT height_cm FROM players WHERE player_id = ?),
                            weight_kg = (SELECT weight_kg FROM players WHERE player_id = ?),
                            primary_position = (SELECT primary_position FROM players WHERE player_id = ?),
                            nationality = (SELECT nationality FROM players WHERE player_id = ?),
                            image_url = (SELECT image_url FROM players WHERE player_id = ?),
                            profile_url = (SELECT profile_url FROM players WHERE player_id = ?)
                        WHERE player_id = ?
                    ''', (source_pid,) * 8 + (pid,))
                    
                    enriched += 1
                    matches_found += 1
                    
                    if enriched <= 10:
                        print(f'  ✓ "{name}" <- "{source_name}" (multi-match)')
                    break
    
    conn.commit()
    
    # 4. Finale Statistik
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            COUNT(nationality) as has_nat,
            COUNT(height_cm) as has_height
        FROM players
    ''')
    
    total, has_nat, has_height = cursor.fetchone()
    
    print(f'\n' + '='*80)
    print('ENRICHMENT ABGESCHLOSSEN')
    print('='*80)
    print(f'\nVorher: ~521 Spieler mit Profil-Daten')
    print(f'Jetzt:  {has_nat} Spieler mit Nationalität ({100*has_nat/total:.1f}%)')
    print(f'        {has_height} Spieler mit Größe ({100*has_height/total:.1f}%)')
    print(f'\n✓ {enriched} Spieler angereichert durch intelligentes Name-Matching')
    
    # Zeige Beispiele
    print(f'\nBeispiele:')
    cursor.execute('''
        SELECT name, nationality, primary_position, height_cm
        FROM players
        WHERE name IN ('Burkardt', 'Renner', 'Hönnscheidt', 'Christ', 'Iser')
        ORDER BY name
    ''')
    
    for name, nat, pos, height in cursor.fetchall():
        status = '✓' if nat else '✗'
        print(f'  {status} {name:<20} Nat: {nat if nat else "FEHLT":<15} Pos: {pos if pos else "FEHLT":<20}')
    
    conn.close()

if __name__ == '__main__':
    enrich_players_smart('fsv_archive_complete.db')

