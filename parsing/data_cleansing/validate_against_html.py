#!/usr/bin/env python3
"""
Script zur Validierung von Fehlern gegen HTML-Rohdaten.

Für jeden problematischen Eintrag:
- Finde zugehörige HTML-Dateien
- Extrahiere korrekten Namen aus HTML
- Vergleiche mit Datenbank-Eintrag
- Dokumentiere Parsing-Fehler
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from config import Config


def normalize_whitespace(value: str) -> str:
    """Normalisiere Whitespace."""
    return re.sub(r"\s+", " ", value.strip())


def read_html(path: Path) -> Optional[BeautifulSoup]:
    """Lese HTML-Datei."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="latin-1", errors="ignore") as handle:
            return BeautifulSoup(handle.read(), "lxml")
    except Exception as e:
        return None


class HTMLValidator:
    """Validiert Datenbank-Einträge gegen HTML-Rohdaten."""
    
    def __init__(self, db_config: Config, base_path: Path, errors_file: str):
        self.config = db_config
        self.base_path = base_path
        self.errors_file = errors_file
        self.errors: List[Dict] = []
        self.validated_errors: List[Dict] = []
        
    def connect(self):
        """Stelle Verbindung zur Datenbank her."""
        self.conn = psycopg2.connect(self.config.build_psycopg2_dsn())
        self.cur = self.conn.cursor()
        
    def close(self):
        """Schließe Datenbankverbindung."""
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def load_errors(self):
        """Lade dokumentierte Fehler."""
        errors_path = Path(self.errors_file)
        if not errors_path.exists():
            print(f"❌ Fehlerdatei nicht gefunden: {self.errors_file}")
            return
        
        with errors_path.open('r', encoding='utf-8') as f:
            self.errors = json.load(f)
        
        print(f"📂 {len(self.errors):,} Fehler geladen")
    
    def find_player_html(self, player_id: int, name: str, profile_url: Optional[str]) -> Optional[Path]:
        """Finde HTML-Datei für einen Spieler."""
        if profile_url:
            html_path = self.base_path / profile_url
            if html_path.exists():
                return html_path
        
        player_dir = self.base_path / "spieler"
        if player_dir.exists():
            normalized_name = name.lower().replace(" ", "").replace("-", "").replace(".", "")
            for html_file in player_dir.glob("*.html"):
                stem_normalized = html_file.stem.lower().replace(" ", "").replace("-", "").replace(".", "")
                if normalized_name in stem_normalized or stem_normalized in normalized_name:
                    return html_file
        
        return None
    
    def extract_correct_player_name_from_html(self, html_path: Path) -> Optional[str]:
        """Extrahiere korrekten Spielernamen aus HTML."""
        soup = read_html(html_path)
        if not soup:
            return None
        
        header = soup.find("b")
        if header:
            name = normalize_whitespace(header.get_text(" ", strip=True))
            if name and len(name) > 2:
                return name
        
        return html_path.stem
    
    def validate_player_error(self, error: Dict) -> Dict:
        """Validiere einen Spieler-Fehler gegen HTML."""
        player_id = error['entity_id']
        incorrect_name = error['incorrect_name']
        profile_url = error.get('profile_url')
        
        validated = error.copy()
        validated['html_validation'] = {
            'html_file_found': False,
            'correct_name_from_html': None,
        }
        
        html_path = self.find_player_html(player_id, incorrect_name, profile_url)
        
        if html_path:
            validated['html_validation']['html_file_found'] = True
            validated['html_validation']['html_file'] = str(html_path.relative_to(self.base_path))
            
            correct_name = self.extract_correct_player_name_from_html(html_path)
            if correct_name:
                validated['html_validation']['correct_name_from_html'] = correct_name
                validated['correct_name'] = correct_name
                
                if correct_name.lower() != incorrect_name.lower():
                    validated['html_validation']['parsing_error_confirmed'] = True
        
        return validated
    
    def validate_referee_error(self, error: Dict) -> Dict:
        """Validiere einen Schiedsrichter-Fehler gegen HTML."""
        incorrect_name = error['incorrect_name']
        profile_url = error.get('profile_url')
        
        validated = error.copy()
        validated['html_validation'] = {
            'html_file_found': False,
            'correct_name_from_html': None,
        }
        
        if profile_url:
            html_path = self.base_path / profile_url
            if html_path.exists():
                validated['html_validation']['html_file_found'] = True
                validated['html_validation']['html_file'] = str(html_path.relative_to(self.base_path))
                
                soup = read_html(html_path)
                if soup:
                    header = soup.find("b")
                    if header:
                        correct_name = normalize_whitespace(header.get_text(" ", strip=True))
                        validated['html_validation']['correct_name_from_html'] = correct_name
                        validated['correct_name'] = correct_name
        
        if incorrect_name.startswith("Schiedsrichterin:"):
            corrected = incorrect_name.replace("Schiedsrichterin:", "").strip()
            if corrected:
                validated['correct_name'] = corrected
                validated['html_validation']['parsing_error_confirmed'] = True
        
        return validated
    
    def validate_all_errors(self, limit: Optional[int] = None):
        """Validiere alle Fehler gegen HTML."""
        print("\n" + "=" * 80)
        print("HTML-VALIDIERUNG")
        print("=" * 80)
        
        errors_to_validate = self.errors[:limit] if limit else self.errors
        
        for i, error in enumerate(errors_to_validate, 1):
            entity_type = error['entity_type']
            
            if i % 100 == 0:
                print(f"  Fortschritt: {i}/{len(errors_to_validate)}...")
            
            if entity_type == 'player':
                validated = self.validate_player_error(error)
            elif entity_type == 'referee':
                validated = self.validate_referee_error(error)
            else:
                validated = error.copy()
                validated['html_validation'] = {'skipped': True}
            
            self.validated_errors.append(validated)
        
        print(f"\n✓ {len(self.validated_errors):,} Fehler validiert")
    
    def save_validated_errors(self, output_file: str):
        """Speichere validierte Fehler."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(self.validated_errors, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Validierte Fehler gespeichert in: {output_file}")
        
        html_found = sum(1 for e in self.validated_errors 
                        if e.get('html_validation', {}).get('html_file_found'))
        correct_names_found = sum(1 for e in self.validated_errors 
                                 if e.get('correct_name'))
        parsing_confirmed = sum(1 for e in self.validated_errors 
                               if e.get('html_validation', {}).get('parsing_error_confirmed'))
        
        print(f"\n📊 STATISTIK:")
        print(f"  HTML-Dateien gefunden: {html_found:,}")
        print(f"  Korrekte Namen extrahiert: {correct_names_found:,}")
        print(f"  Parsing-Fehler bestätigt: {parsing_confirmed:,}")


def main():
    """Hauptfunktion."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validiere Fehler gegen HTML-Rohdaten')
    parser.add_argument('--errors-file', default='data_cleansing/identified_errors.json',
                       help='Pfad zur Fehlerdatei')
    parser.add_argument('--base-path', default='fsvarchiv',
                       help='Basis-Pfad zum HTML-Archiv')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limitiere Anzahl zu validierender Fehler')
    
    args = parser.parse_args()
    
    config = Config()
    base_path = Path(args.base_path)
    
    validator = HTMLValidator(config, base_path, args.errors_file)
    
    try:
        validator.connect()
        validator.load_errors()
        validator.validate_all_errors(limit=args.limit)
        
        output_file = 'data_cleansing/validated_errors.json'
        validator.save_validated_errors(output_file)
        
    except Exception as e:
        print(f"\n❌ FEHLER: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        validator.close()


if __name__ == '__main__':
    main()

