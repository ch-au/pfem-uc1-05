#!/usr/bin/env python3
"""
Script zur Analyse dokumentierter Fehler und Erstellung eines Parser-Verbesserungsplans.

Analysiert dokumentierte Fehler:
- Gruppiert nach Fehlertyp
- Identifiziert wiederkehrende Patterns
- Erstellt Liste von Parser-Verbesserungen
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class ErrorAnalyzer:
    """Analysiert dokumentierte Fehler und erstellt Verbesserungsplan."""
    
    def __init__(self, validated_errors_file: str):
        self.validated_errors_file = validated_errors_file
        self.errors: List[Dict] = []
        self.analysis: Dict = {}
        
    def load_errors(self):
        """Lade validierte Fehler."""
        errors_path = Path(self.validated_errors_file)
        if not errors_path.exists():
            print(f"❌ Fehlerdatei nicht gefunden: {self.validated_errors_file}")
            return
        
        with errors_path.open('r', encoding='utf-8') as f:
            self.errors = json.load(f)
        
        print(f"📂 {len(self.errors):,} Fehler geladen")
    
    def analyze_errors(self):
        """Analysiere Fehler und erstelle Verbesserungsplan."""
        print("\n" + "=" * 80)
        print("FEHLER-ANALYSE")
        print("=" * 80)
        
        # Gruppiere nach Fehlerkategorie
        by_category = defaultdict(list)
        by_entity_type = defaultdict(list)
        by_parsing_method = defaultdict(list)
        
        for error in self.errors:
            category = error.get('error_category', 'unknown')
            entity_type = error.get('entity_type', 'unknown')
            parsing_method = error.get('parsing_method', 'unknown')
            
            by_category[category].append(error)
            by_entity_type[entity_type].append(error)
            if parsing_method:
                by_parsing_method[parsing_method].append(error)
        
        self.analysis = {
            'total_errors': len(self.errors),
            'by_category': {k: len(v) for k, v in by_category.items()},
            'by_entity_type': {k: len(v) for k, v in by_entity_type.items()},
            'by_parsing_method': {k: len(v) for k, v in by_parsing_method.items()},
            'parser_improvements': self._generate_parser_improvements(by_category, by_parsing_method),
            'examples': self._extract_examples(by_category),
        }
        
        print(f"\n📊 FEHLER-VERTEILUNG:")
        print(f"  Nach Kategorie:")
        for category, count in sorted(self.analysis['by_category'].items(), key=lambda x: -x[1]):
            print(f"    - {category}: {count:,}")
        print(f"  Nach Entitätstyp:")
        for entity_type, count in sorted(self.analysis['by_entity_type'].items(), key=lambda x: -x[1]):
            print(f"    - {entity_type}: {count:,}")
        print(f"  Nach Parsing-Methode:")
        for method, count in sorted(self.analysis['by_parsing_method'].items(), key=lambda x: -x[1]):
            print(f"    - {method}: {count:,}")
    
    def _generate_parser_improvements(self, by_category: Dict, by_parsing_method: Dict) -> List[Dict]:
        """Generiere Liste von Parser-Verbesserungen."""
        improvements = []
        
        # 1. Trainer-Namen Filterung
        if 'trainer_name' in by_category:
            improvements.append({
                'priority': 'high',
                'method': 'get_or_create_player',
                'issue': 'Trainer-Namen werden als Spieler erkannt',
                'count': len(by_category['trainer_name']),
                'fix': 'Add validation: Check if name contains "Trainer:", "FSV-Trainer", "Coach" before creating player',
                'code_location': 'comprehensive_fsv_parser.py:579 (get_or_create_player)',
                'example_errors': [e['incorrect_name'] for e in list(by_category['trainer_name'])[:5]],
            })
        
        # 2. Schiedsrichter-Namen Filterung
        if 'referee_name' in by_category:
            improvements.append({
                'priority': 'high',
                'method': 'get_or_create_player',
                'issue': 'Schiedsrichter-Namen werden als Spieler erkannt',
                'count': len(by_category['referee_name']),
                'fix': 'Add validation: Check if name contains "Schiedsrichter:", "Schiedsrichterin:" before creating player',
                'code_location': 'comprehensive_fsv_parser.py:579 (get_or_create_player)',
                'example_errors': [e['incorrect_name'] for e in list(by_category['referee_name'])[:5]],
            })
        
        # 3. Tor-Text Parsing
        if 'goal_text' in by_category:
            improvements.append({
                'priority': 'high',
                'method': 'parse_goal_table',
                'issue': 'Vollständiger Tor-Text wird als Spielername erkannt',
                'count': len(by_category['goal_text']),
                'fix': 'Improve parse_goal_table: Extract only player name from goal text, not full "Tore 11. 0:1 ..." text',
                'code_location': 'comprehensive_fsv_parser.py:2104 (parse_goal_table)',
                'example_errors': [e['incorrect_name'] for e in list(by_category['goal_text'])[:5]],
            })
        
        # 4. Fehlertext in Substitutionen
        if 'error_text' in by_category:
            improvements.append({
                'priority': 'medium',
                'method': 'parse_substitution_entry',
                'issue': 'Fehlertext ("FE,", "ET,", "HE,") wird als Spielername erkannt',
                'count': len(by_category['error_text']),
                'fix': 'Improve parse_substitution_entry: Filter prefixes "FE,", "ET,", "HE," before extracting player names',
                'code_location': 'comprehensive_fsv_parser.py:2049 (parse_substitution_entry)',
                'example_errors': [e['incorrect_name'] for e in list(by_category['error_text'])[:5]],
            })
        
        # 5. Komma in Namen
        if 'contains_comma' in by_category:
            improvements.append({
                'priority': 'medium',
                'method': 'get_or_create_player',
                'issue': 'Namen enthalten Kommas (oft Parsing-Fehler)',
                'count': len(by_category['contains_comma']),
                'fix': 'Add validation: Warn or reject player names containing commas (unless it\'s a known pattern)',
                'code_location': 'comprehensive_fsv_parser.py:579 (get_or_create_player)',
                'example_errors': [e['incorrect_name'] for e in list(by_category['contains_comma'])[:5]],
            })
        
        # 6. Ungültige Patterns
        if 'invalid_pattern' in by_category:
            improvements.append({
                'priority': 'medium',
                'method': 'get_or_create_player',
                'issue': 'Namen beginnen mit ungültigen Zeichen oder sind zu kurz',
                'count': len(by_category['invalid_pattern']),
                'fix': 'Add validation: Reject names starting with non-letters, single characters, or only numbers',
                'code_location': 'comprehensive_fsv_parser.py:579 (get_or_create_player)',
                'example_errors': [e['incorrect_name'] for e in list(by_category['invalid_pattern'])[:5]],
            })
        
        # 7. Team-Block Parsing
        if 'parse_team_block' in by_parsing_method:
            improvements.append({
                'priority': 'high',
                'method': 'parse_team_block',
                'issue': 'Trainer-Namen werden aus Team-Block als Spieler extrahiert',
                'count': len(by_parsing_method['parse_team_block']),
                'fix': 'Improve parse_team_block: Filter out cells containing "Trainer:", "FSV-Trainer" before processing',
                'code_location': 'comprehensive_fsv_parser.py:2004 (parse_team_block)',
                'example_errors': [e['incorrect_name'] for e in list(by_parsing_method['parse_team_block'])[:10]],
            })
        
        return improvements
    
    def _extract_examples(self, by_category: Dict) -> Dict[str, List[str]]:
        """Extrahiere Beispiele für jede Kategorie."""
        examples = {}
        for category, errors in by_category.items():
            examples[category] = [
                {
                    'incorrect_name': e['incorrect_name'],
                    'correct_name': e.get('correct_name'),
                    'parsing_method': e.get('parsing_method'),
                }
                for e in errors[:10]
            ]
        return examples
    
    def save_analysis(self, output_file: str):
        """Speichere Analyse."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(self.analysis, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Analyse gespeichert in: {output_file}")
    
    def generate_markdown_report(self, output_file: str):
        """Generiere Markdown-Report mit Verbesserungsplan."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open('w', encoding='utf-8') as f:
            f.write("# Parser-Verbesserungsplan\n\n")
            f.write(f"Basierend auf Analyse von {self.analysis['total_errors']:,} dokumentierten Fehlern.\n\n")
            
            f.write("## Übersicht\n\n")
            f.write(f"- **Gesamtfehler**: {self.analysis['total_errors']:,}\n")
            f.write(f"- **Verbesserungen vorgeschlagen**: {len(self.analysis['parser_improvements'])}\n\n")
            
            f.write("## Fehler-Verteilung\n\n")
            f.write("### Nach Kategorie\n\n")
            for category, count in sorted(self.analysis['by_category'].items(), key=lambda x: -x[1]):
                f.write(f"- **{category}**: {count:,}\n")
            
            f.write("\n### Nach Parsing-Methode\n\n")
            for method, count in sorted(self.analysis['by_parsing_method'].items(), key=lambda x: -x[1]):
                f.write(f"- **{method}**: {count:,}\n")
            
            f.write("\n## Parser-Verbesserungen\n\n")
            for i, improvement in enumerate(self.analysis['parser_improvements'], 1):
                f.write(f"### {i}. {improvement['issue']}\n\n")
                f.write(f"- **Priorität**: {improvement['priority']}\n")
                f.write(f"- **Betroffene Methode**: `{improvement['method']}`\n")
                f.write(f"- **Anzahl Fehler**: {improvement['count']:,}\n")
                f.write(f"- **Code-Stelle**: {improvement['code_location']}\n")
                f.write(f"- **Lösung**: {improvement['fix']}\n")
                f.write(f"- **Beispiele**:\n")
                for example in improvement['example_errors']:
                    f.write(f"  - `{example}`\n")
                f.write("\n")
            
            f.write("## Beispiele nach Kategorie\n\n")
            for category, examples in self.analysis['examples'].items():
                f.write(f"### {category}\n\n")
                for example in examples[:5]:
                    f.write(f"- **Falsch**: `{example['incorrect_name']}`\n")
                    if example.get('correct_name'):
                        f.write(f"  - **Korrekt**: `{example['correct_name']}`\n")
                    if example.get('parsing_method'):
                        f.write(f"  - **Methode**: `{example['parsing_method']}`\n")
                f.write("\n")
        
        print(f"📄 Markdown-Report gespeichert in: {output_file}")


def main():
    """Hauptfunktion."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analysiere Fehler und erstelle Verbesserungsplan')
    parser.add_argument('--validated-errors-file', default='data_cleansing/validated_errors.json',
                       help='Pfad zur validierten Fehlerdatei')
    parser.add_argument('--output-analysis', default='data_cleansing/error_analysis.json',
                       help='Ausgabedatei für Analyse')
    parser.add_argument('--output-markdown', default='data_cleansing/parser_improvements.md',
                       help='Ausgabedatei für Markdown-Report')
    
    args = parser.parse_args()
    
    analyzer = ErrorAnalyzer(args.validated_errors_file)
    
    try:
        analyzer.load_errors()
        analyzer.analyze_errors()
        analyzer.save_analysis(args.output_analysis)
        analyzer.generate_markdown_report(args.output_markdown)
        
    except Exception as e:
        print(f"\n❌ FEHLER: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

