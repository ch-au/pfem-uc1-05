#!/usr/bin/env python3
"""
Upgrade existing database with coach profile data
"""
import sqlite3
from pathlib import Path
from bs4 import BeautifulSoup
import re
from datetime import datetime

def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())

def read_html(path: Path):
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="latin-1", errors="ignore") as handle:
            return BeautifulSoup(handle.read(), "lxml")
    except OSError:
        return None

def upgrade_database(db_path: str, base_path: str = "fsvarchiv"):
    """Upgrade database schema and enrich coach data"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('='*80)
    print('COACHES SCHEMA UPGRADE & ENRICHMENT')
    print('='*80)
    
    # 1. Erweitere coaches Tabelle
    print('\n1. Erweitere coaches Tabelle...')
    
    try:
        cursor.execute('ALTER TABLE coaches ADD COLUMN birth_date TEXT')
        print('   ✓ birth_date hinzugefügt')
    except sqlite3.OperationalError:
        print('   • birth_date existiert bereits')
    
    try:
        cursor.execute('ALTER TABLE coaches ADD COLUMN birth_place TEXT')
        print('   ✓ birth_place hinzugefügt')
    except sqlite3.OperationalError:
        print('   • birth_place existiert bereits')
    
    try:
        cursor.execute('ALTER TABLE coaches ADD COLUMN nationality TEXT')
        print('   ✓ nationality hinzugefügt')
    except sqlite3.OperationalError:
        print('   • nationality existiert bereits')
    
    # 2. Erstelle coach_careers Tabelle
    print('\n2. Erstelle coach_careers Tabelle...')
    
    try:
        cursor.execute('''
            CREATE TABLE coach_careers (
                career_id INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id INTEGER,
                team_name TEXT,
                start_date TEXT,
                end_date TEXT,
                role TEXT,
                FOREIGN KEY (coach_id) REFERENCES coaches(coach_id)
            )
        ''')
        print('   ✓ coach_careers Tabelle erstellt')
    except sqlite3.OperationalError:
        print('   • coach_careers existiert bereits')
        cursor.execute('DELETE FROM coach_careers')
        print('   ✓ Alte Einträge gelöscht')
    
    conn.commit()
    
    # 3. Parse alle Coach-Profile
    print('\n3. Parse Trainer-Profile...')
    
    trainer_dir = Path(base_path) / "trainer"
    if not trainer_dir.exists():
        print('   ✗ trainer/ Verzeichnis nicht gefunden')
        return
    
    coach_files = list(trainer_dir.glob("*.html"))
    print(f'   Gefunden: {len(coach_files)} Trainer-Profile')
    
    enriched = 0
    for i, coach_file in enumerate(coach_files, 1):
        soup = read_html(coach_file)
        if soup is None:
            continue
        
        # Get coach name
        header = soup.find("b")
        if not header:
            continue
        
        profile_name = normalize_whitespace(header.get_text(" ", strip=True))
        
        # Extract last name for matching
        last_name_parts = profile_name.split()
        last_name = last_name_parts[-1] if last_name_parts else ""
        
        # Find coach in DB
        cursor.execute(
            "SELECT coach_id, name FROM coaches WHERE name LIKE ?",
            (f"%{last_name}%",)
        )
        matches = cursor.fetchall()
        
        if not matches:
            continue
        
        # Parse profile data
        information = soup.get_text("\n", strip=True)
        
        # Birth date and place
        birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n.]+)", information, re.DOTALL)
        birth_date = None
        birth_place = None
        if birth_match:
            try:
                birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
            birth_place = birth_match.group(2).strip()
        
        # Nationality
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
        
        # Enrich all matching coaches
        for coach_id, existing_name in matches:
            cursor.execute('''
                UPDATE coaches
                SET birth_date = COALESCE(?, birth_date),
                    birth_place = COALESCE(?, birth_place),
                    nationality = COALESCE(?, nationality)
                WHERE coach_id = ?
            ''', (birth_date, birth_place, nationality, coach_id))
            
            # Parse career
            career_header = soup.find("b", string=re.compile("Laufbahn", re.IGNORECASE))
            if career_header:
                career_table = career_header.find_next("table")
                if career_table:
                    cursor.execute("DELETE FROM coach_careers WHERE coach_id = ?", (coach_id,))
                    for row in career_table.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) < 5:
                            continue
                        
                        start_date = normalize_whitespace(cells[0].get_text(" ", strip=True))
                        end_date = normalize_whitespace(cells[2].get_text(" ", strip=True))
                        team_text = normalize_whitespace(cells[4].get_text(" ", strip=True)) if len(cells) > 4 else None
                        role_text = normalize_whitespace(cells[6].get_text(" ", strip=True)) if len(cells) > 6 else None
                        
                        if team_text:
                            cursor.execute('''
                                INSERT INTO coach_careers (coach_id, team_name, start_date, end_date, role)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (coach_id, team_text, start_date, end_date, role_text))
            
            enriched += 1
            if enriched <= 10:
                print(f'   ✓ {existing_name} <- {profile_name}')
                if birth_date:
                    print(f'      Geburt: {birth_date}, {birth_place if birth_place else "?"}')
    
    conn.commit()
    
    # Statistik
    cursor.execute('SELECT COUNT(*), COUNT(birth_date), COUNT(nationality) FROM coaches')
    result = cursor.fetchone()
    total, has_birth, has_nat = result[0], result[1], result[2]
    
    cursor.execute('SELECT COUNT(*) FROM coach_careers')
    career_count = cursor.fetchone()[0]
    
    print(f'\n' + '='*80)
    print('UPGRADE ABGESCHLOSSEN')
    print('='*80)
    print(f'\nTrainer: {total}')
    print(f'  Mit Geburtsdatum: {has_birth}')
    print(f'  Mit Nationalität: {has_nat}')
    print(f'Laufbahn-Einträge: {career_count}')
    print(f'\n✓ {enriched} Trainer angereichert')
    
    conn.close()

if __name__ == '__main__':
    upgrade_database('fsv_archive_complete.db')

