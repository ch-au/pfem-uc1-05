#!/usr/bin/env python3
"""
Script zur Identifikation und Dokumentation von Fehlern in zentralen Tabellen.

Identifiziert problematische Einträge in Players, Teams, Coaches, Referees
und dokumentiert jeden Fehler mit Quelle, Kontext und Kategorie.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from config import Config


class ErrorDocumenter:
    """Identifiziert und dokumentiert Fehler in Datenbank-Einträgen."""
    
    # Fehler-Patterns
    TRAINER_PATTERNS = [
        r'trainer',
        r'coach',
        r'fsv-trainer',
        r'trainer:',
    ]
    
    REFEREE_PATTERNS = [
        r'schiedsrichter',
        r'referee',
        r'schiedsrichterin',
        r'schiedsrichter:',
    ]
    
    GOAL_TEXT_PATTERNS = [
        r'^tore\s+',
        r'^\d+\.\s*\d+:\d+',
        r'^tore\s+\d+',
    ]
    
    ERROR_TEXT_PATTERNS = [
        r'^FE,\s*',
        r'^ET,\s*',
        r'^HE,\s*',
        r',\s*(liebers|latza|hazard|klopp)',
    ]
    
    INVALID_PATTERNS = [
        r'^[^a-zA-Z]',  # Beginnt nicht mit Buchstabe
        r'^\d+$',  # Nur Zahlen
        r'^[A-Z]{1,3}$',  # Nur Großbuchstaben (Abkürzungen)
    ]
    
    def __init__(self, db_config: Config):
        self.config = db_config
        self.errors: List[Dict] = []
        
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
    
    def categorize_error(self, name: str, entity_type: str) -> Optional[str]:
        """Kategorisiere einen Fehler basierend auf Patterns."""
        name_lower = name.lower()
        
        # Trainer-Namen
        if any(re.search(pattern, name_lower) for pattern in self.TRAINER_PATTERNS):
            return 'trainer_name'
        
        # Schiedsrichter-Namen
        if any(re.search(pattern, name_lower) for pattern in self.REFEREE_PATTERNS):
            return 'referee_name'
        
        # Tor-Text
        if any(re.search(pattern, name_lower) for pattern in self.GOAL_TEXT_PATTERNS):
            return 'goal_text'
        
        # Fehlertext
        if any(re.search(pattern, name_lower) for pattern in self.ERROR_TEXT_PATTERNS):
            return 'error_text'
        
        # Ungültige Patterns
        if any(re.search(pattern, name) for pattern in self.INVALID_PATTERNS):
            return 'invalid_pattern'
        
        # Zu lang
        if len(name) > 100:
            return 'too_long'
        
        # Enthält Komma (oft Fehler)
        if ',' in name and entity_type == 'player':
            return 'contains_comma'
        
        return None
    
    def find_source_context(self, entity_type: str, entity_id: int, name: str) -> Dict[str, Optional[str]]:
        """Versuche Quelle und Kontext für einen Fehler zu finden."""
        context = {
            'source_file': None,
            'source_context': None,
            'parsing_method': None,
        }
        
        if entity_type == 'player':
            # Suche in match_lineups
            self.cur.execute("""
                SELECT m.match_id, ml.is_starter, ml.shirt_number
                FROM public.match_lineups ml
                JOIN public.matches m ON ml.match_id = m.match_id
                WHERE ml.player_id = %s
                LIMIT 1
            """, (entity_id,))
            result = self.cur.fetchone()
            if result:
                context['source_context'] = f'Match lineup (match_id={result[0]}, starter={result[1]}, shirt={result[2]})'
                context['parsing_method'] = 'parse_team_block'
                return context
            
            # Suche in goals
            self.cur.execute("""
                SELECT m.match_id, g.minute, g.event_type
                FROM public.goals g
                JOIN public.matches m ON g.match_id = m.match_id
                WHERE g.player_id = %s OR g.assist_player_id = %s
                LIMIT 1
            """, (entity_id, entity_id))
            result = self.cur.fetchone()
            if result:
                context['source_context'] = f'Goal/Assist (match_id={result[0]}, minute={result[1]}, type={result[2]})'
                context['parsing_method'] = 'parse_goal_table'
                return context
            
            # Suche in substitutions
            self.cur.execute("""
                SELECT m.match_id, ms.minute
                FROM public.match_substitutions ms
                JOIN public.matches m ON ms.match_id = m.match_id
                WHERE ms.player_on_id = %s OR ms.player_off_id = %s
                LIMIT 1
            """, (entity_id, entity_id))
            result = self.cur.fetchone()
            if result:
                context['source_context'] = f'Substitution (match_id={result[0]}, minute={result[1]})'
                context['parsing_method'] = 'parse_substitution_entry'
                return context
        
        elif entity_type == 'referee':
            # Suche in matches
            self.cur.execute("""
                SELECT m.match_id, m.match_date
                FROM public.matches m
                JOIN public.match_referees mr ON m.match_id = mr.match_id
                WHERE mr.referee_id = %s
                LIMIT 1
            """, (entity_id,))
            result = self.cur.fetchone()
            if result:
                context['source_context'] = f'Match referee (match_id={result[0]}, date={result[1]})'
                context['parsing_method'] = 'extract_match_details'
                return context
        
        return context
    
    def identify_player_errors(self):
        """Identifiziere Fehler in Players-Tabelle."""
        print("🔍 Analysiere Players...")
        
        self.cur.execute("""
            SELECT player_id, name, profile_url
            FROM public.players
            ORDER BY player_id
        """)
        
        total = 0
        errors_found = 0
        
        for row in self.cur.fetchall():
            total += 1
            player_id, name, profile_url = row
            
            if not name or not name.strip():
                continue
            
            error_category = self.categorize_error(name, 'player')
            
            if error_category:
                errors_found += 1
                context = self.find_source_context('player', player_id, name)
                
                error_doc = {
                    'entity_type': 'player',
                    'entity_id': player_id,
                    'incorrect_name': name,
                    'error_category': error_category,
                    'profile_url': profile_url,
                    'source_file': context.get('source_file'),
                    'source_context': context.get('source_context'),
                    'parsing_method': context.get('parsing_method'),
                    'correct_name': None,  # Wird später durch HTML-Validierung gefüllt
                    'should_delete': error_category in ['trainer_name', 'referee_name', 'goal_text', 'error_text'],
                    'parser_fix_needed': self._suggest_parser_fix(error_category),
                }
                
                self.errors.append(error_doc)
                
                if errors_found <= 10:  # Zeige erste 10 Fehler
                    print(f"  ❌ {player_id}: '{name}' [{error_category}]")
        
        print(f"  ✓ {errors_found:,} von {total:,} Spielern haben Probleme ({errors_found/total*100:.1f}%)")
        return errors_found
    
    def identify_referee_errors(self):
        """Identifiziere Fehler in Referees-Tabelle."""
        print("🔍 Analysiere Referees...")
        
        self.cur.execute("""
            SELECT referee_id, name, profile_url
            FROM public.referees
            ORDER BY referee_id
        """)
        
        total = 0
        errors_found = 0
        
        for row in self.cur.fetchall():
            total += 1
            referee_id, name, profile_url = row
            
            if not name or not name.strip():
                continue
            
            error_category = self.categorize_error(name, 'referee')
            
            if error_category:
                errors_found += 1
                context = self.find_source_context('referee', referee_id, name)
                
                error_doc = {
                    'entity_type': 'referee',
                    'entity_id': referee_id,
                    'incorrect_name': name,
                    'error_category': error_category,
                    'profile_url': profile_url,
                    'source_file': context.get('source_file'),
                    'source_context': context.get('source_context'),
                    'parsing_method': context.get('parsing_method'),
                    'correct_name': None,
                    'should_delete': error_category in ['trainer_name', 'goal_text', 'error_text'],
                    'parser_fix_needed': self._suggest_parser_fix(error_category),
                }
                
                self.errors.append(error_doc)
                
                if errors_found <= 10:
                    print(f"  ❌ {referee_id}: '{name}' [{error_category}]")
        
        print(f"  ✓ {errors_found:,} von {total:,} Schiedsrichtern haben Probleme ({errors_found/total*100:.1f}%)")
        return errors_found
    
    def identify_team_errors(self):
        """Identifiziere Fehler in Teams-Tabelle."""
        print("🔍 Analysiere Teams...")
        
        self.cur.execute("""
            SELECT team_id, name
            FROM public.teams
            ORDER BY team_id
        """)
        
        total = 0
        errors_found = 0
        
        for row in self.cur.fetchall():
            total += 1
            team_id, name = row
            
            if not name or not name.strip():
                continue
            
            error_category = self.categorize_error(name, 'team')
            
            if error_category:
                errors_found += 1
                
                error_doc = {
                    'entity_type': 'team',
                    'entity_id': team_id,
                    'incorrect_name': name,
                    'error_category': error_category,
                    'source_file': None,
                    'source_context': None,
                    'parsing_method': None,
                    'correct_name': None,
                    'should_delete': False,
                    'parser_fix_needed': self._suggest_parser_fix(error_category),
                }
                
                self.errors.append(error_doc)
        
        print(f"  ✓ {errors_found:,} von {total:,} Teams haben Probleme ({errors_found/total*100:.1f}%)")
        return errors_found
    
    def identify_coach_errors(self):
        """Identifiziere Fehler in Coaches-Tabelle."""
        print("🔍 Analysiere Coaches...")
        
        self.cur.execute("""
            SELECT coach_id, name, profile_url
            FROM public.coaches
            ORDER BY coach_id
        """)
        
        total = 0
        errors_found = 0
        
        for row in self.cur.fetchall():
            total += 1
            coach_id, name, profile_url = row
            
            if not name or not name.strip():
                continue
            
            error_category = self.categorize_error(name, 'coach')
            
            if error_category:
                errors_found += 1
                
                error_doc = {
                    'entity_type': 'coach',
                    'entity_id': coach_id,
                    'incorrect_name': name,
                    'error_category': error_category,
                    'profile_url': profile_url,
                    'source_file': None,
                    'source_context': None,
                    'parsing_method': None,
                    'correct_name': None,
                    'should_delete': False,
                    'parser_fix_needed': self._suggest_parser_fix(error_category),
                }
                
                self.errors.append(error_doc)
        
        print(f"  ✓ {errors_found:,} von {total:,} Trainer haben Probleme ({errors_found/total*100:.1f}%)")
        return errors_found
    
    def _suggest_parser_fix(self, error_category: str) -> str:
        """Schlage Parser-Verbesserung basierend auf Fehlerkategorie vor."""
        fixes = {
            'trainer_name': 'Filter trainer names before creating player (check for "Trainer:", "FSV-Trainer")',
            'referee_name': 'Filter referee names before creating player (check for "Schiedsrichter:")',
            'goal_text': 'Better parsing of goal table - extract only player names, not full goal text',
            'error_text': 'Better parsing of substitution entries - filter "FE,", "ET,", "HE," prefixes',
            'contains_comma': 'Validate player names - commas usually indicate parsing errors',
            'too_long': 'Add maximum length validation for names',
            'invalid_pattern': 'Add pattern validation - names should start with letters',
        }
        return fixes.get(error_category, 'Review manually')
    
    def save_errors(self, output_file: str):
        """Speichere dokumentierte Fehler in JSON-Datei."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(self.errors, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 {len(self.errors):,} Fehler dokumentiert in: {output_file}")
        
        # Erstelle auch Zusammenfassung
        summary = {
            'total_errors': len(self.errors),
            'by_entity_type': {},
            'by_error_category': {},
        }
        
        for error in self.errors:
            entity_type = error['entity_type']
            category = error['error_category']
            
            summary['by_entity_type'][entity_type] = summary['by_entity_type'].get(entity_type, 0) + 1
            summary['by_error_category'][category] = summary['by_error_category'].get(category, 0) + 1
        
        summary_path = output_path.parent / f"{output_path.stem}_summary.json"
        with summary_path.open('w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"📊 Zusammenfassung gespeichert in: {summary_path}")
        return summary


def main():
    """Hauptfunktion."""
    print("=" * 80)
    print("FEHLER-IDENTIFIKATION & DOKUMENTATION")
    print("=" * 80)
    
    config = Config()
    documenter = ErrorDocumenter(config)
    
    try:
        documenter.connect()
        
        # Identifiziere Fehler in allen Tabellen
        player_errors = documenter.identify_player_errors()
        referee_errors = documenter.identify_referee_errors()
        team_errors = documenter.identify_team_errors()
        coach_errors = documenter.identify_coach_errors()
        
        total_errors = player_errors + referee_errors + team_errors + coach_errors
        
        print("\n" + "=" * 80)
        print(f"GESAMT: {total_errors:,} Fehler identifiziert")
        print("=" * 80)
        
        # Speichere Fehler
        output_file = 'data_cleansing/identified_errors.json'
        summary = documenter.save_errors(output_file)
        
        print("\n📋 ZUSAMMENFASSUNG:")
        print(f"  Nach Entitätstyp:")
        for entity_type, count in summary['by_entity_type'].items():
            print(f"    - {entity_type}: {count:,}")
        print(f"  Nach Fehlerkategorie:")
        for category, count in sorted(summary['by_error_category'].items(), key=lambda x: -x[1]):
            print(f"    - {category}: {count:,}")
        
    except Exception as e:
        print(f"\n❌ FEHLER: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        documenter.close()


if __name__ == '__main__':
    main()

