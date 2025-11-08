#!/usr/bin/env python3
"""
Script zur automatischen Bereinigung der Datenbank basierend auf dokumentierten Fehlern.

Bereinigt Datenbank-Einträge basierend auf:
- Dokumentierten Fehlern mit should_delete=True
- Korrigierten Namen aus HTML-Validierung
- Validierungsregeln
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from config import Config


class DatabaseCleaner:
    """Bereinigt Datenbank basierend auf dokumentierten Fehlern."""
    
    def __init__(self, db_config: Config, validated_errors_file: str, dry_run: bool = True):
        self.config = db_config
        self.validated_errors_file = validated_errors_file
        self.dry_run = dry_run
        self.errors: List[Dict] = []
        self.cleaning_actions: List[Dict] = []
        
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
        """Lade validierte Fehler."""
        errors_path = Path(self.validated_errors_file)
        if not errors_path.exists():
            print(f"❌ Fehlerdatei nicht gefunden: {self.validated_errors_file}")
            return
        
        with errors_path.open('r', encoding='utf-8') as f:
            self.errors = json.load(f)
        
        print(f"📂 {len(self.errors):,} Fehler geladen")
    
    def clean_player(self, error: Dict) -> Dict:
        """Bereinige einen Spieler-Fehler."""
        player_id = error['entity_id']
        incorrect_name = error['incorrect_name']
        correct_name = error.get('correct_name')
        should_delete = error.get('should_delete', False)
        
        action = {
            'entity_type': 'player',
            'entity_id': player_id,
            'incorrect_name': incorrect_name,
            'action': None,
            'success': False,
        }
        
        # Prüfe ob Spieler noch verwendet wird
        self.cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM public.match_lineups WHERE player_id = %s
                UNION ALL
                SELECT 1 FROM public.goals WHERE player_id = %s OR assist_player_id = %s
                UNION ALL
                SELECT 1 FROM public.match_substitutions WHERE player_on_id = %s OR player_off_id = %s
                UNION ALL
                SELECT 1 FROM public.cards WHERE player_id = %s
            ) AS usage_check
        """, (player_id, player_id, player_id, player_id, player_id, player_id))
        
        usage_count = self.cur.fetchone()[0]
        
        if should_delete and usage_count == 0:
            # Lösche Spieler wenn nicht verwendet
            action['action'] = 'delete'
            if not self.dry_run:
                self.cur.execute("DELETE FROM public.players WHERE player_id = %s", (player_id,))
                action['success'] = True
        elif correct_name and correct_name != incorrect_name:
            # Korrigiere Namen
            action['action'] = 'update'
            action['correct_name'] = correct_name
            if not self.dry_run:
                self.cur.execute(
                    "UPDATE public.players SET name = %s WHERE player_id = %s",
                    (correct_name, player_id)
                )
                action['success'] = True
        elif should_delete and usage_count > 0:
            # Markiere für manuelle Prüfung
            action['action'] = 'needs_review'
            action['usage_count'] = usage_count
        
        return action
    
    def clean_referee(self, error: Dict) -> Dict:
        """Bereinige einen Schiedsrichter-Fehler."""
        referee_id = error['entity_id']
        incorrect_name = error['incorrect_name']
        correct_name = error.get('correct_name')
        
        action = {
            'entity_type': 'referee',
            'entity_id': referee_id,
            'incorrect_name': incorrect_name,
            'action': None,
            'success': False,
        }
        
        if correct_name and correct_name != incorrect_name:
            action['action'] = 'update'
            action['correct_name'] = correct_name
            if not self.dry_run:
                self.cur.execute(
                    "UPDATE public.referees SET name = %s WHERE referee_id = %s",
                    (correct_name, referee_id)
                )
                action['success'] = True
        
        return action
    
    def clean_all(self):
        """Bereinige alle Fehler."""
        print("\n" + "=" * 80)
        print(f"{'DRY RUN - ' if self.dry_run else ''}DATENBANK-BEREINIGUNG")
        print("=" * 80)
        
        players_updated = 0
        players_deleted = 0
        players_needs_review = 0
        referees_updated = 0
        
        for i, error in enumerate(self.errors, 1):
            if i % 100 == 0:
                print(f"  Fortschritt: {i}/{len(self.errors)}...")
            
            entity_type = error['entity_type']
            
            if entity_type == 'player':
                action = self.clean_player(error)
                if action['action'] == 'update':
                    players_updated += 1
                elif action['action'] == 'delete':
                    players_deleted += 1
                elif action['action'] == 'needs_review':
                    players_needs_review += 1
            elif entity_type == 'referee':
                action = self.clean_referee(error)
                if action['action'] == 'update':
                    referees_updated += 1
            else:
                continue
            
            self.cleaning_actions.append(action)
        
        if not self.dry_run:
            self.conn.commit()
        
        print(f"\n✓ Bereinigung abgeschlossen:")
        print(f"  Spieler aktualisiert: {players_updated:,}")
        print(f"  Spieler gelöscht: {players_deleted:,}")
        print(f"  Spieler benötigen Review: {players_needs_review:,}")
        print(f"  Schiedsrichter aktualisiert: {referees_updated:,}")
    
    def save_cleaning_report(self, output_file: str):
        """Speichere Bereinigungs-Report."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(self.cleaning_actions, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Bereinigungs-Report gespeichert in: {output_file}")


def main():
    """Hauptfunktion."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bereinige Datenbank basierend auf dokumentierten Fehlern')
    parser.add_argument('--validated-errors-file', default='data_cleansing/validated_errors.json',
                       help='Pfad zur validierten Fehlerdatei')
    parser.add_argument('--output-report', default='data_cleansing/cleaning_report.json',
                       help='Ausgabedatei für Bereinigungs-Report')
    parser.add_argument('--execute', action='store_true',
                       help='Führe Bereinigung tatsächlich aus (ohne --execute ist es ein Dry Run)')
    
    args = parser.parse_args()
    
    config = Config()
    cleaner = DatabaseCleaner(config, args.validated_errors_file, dry_run=not args.execute)
    
    try:
        cleaner.connect()
        cleaner.load_errors()
        cleaner.clean_all()
        cleaner.save_cleaning_report(args.output_report)
        
        if cleaner.dry_run:
            print("\n⚠️  DRY RUN - Keine Änderungen vorgenommen!")
            print("   Verwende --execute um Bereinigung tatsächlich durchzuführen.")
        
    except Exception as e:
        print(f"\n❌ FEHLER: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleaner.close()


if __name__ == '__main__':
    main()

