# Changelog

## [2025-11] Assist-Text-Filterung & Finale Parser-Verbesserungen

### Neue Features
- **Assist-Text-Filterung**: Assist-Texte wie "FE an Becker" werden jetzt korrekt aufgeteilt
- **Erweiterte Team-Konsolidierung**: Bindestrich-Varianten werden jetzt erkannt ("Reichsbahn-TSV Mainz 05")
- **Assist-Text-Validierung**: Namen mit " an " werden nicht mehr als Spieler erstellt

### Fixes
- **Assist-Parsing**: "FE an Becker" → "Becker" (nur der Teil nach "an")
- **Team-Konsolidierung**: "Reichsbahn-TSV Mainz 05" wird jetzt konsolidiert
- **256 falsche Spieler-Einträge**: Werden beim nächsten Parse automatisch gefiltert

### Geänderte Dateien
- `comprehensive_fsv_parser.py`: 
  - `parse_goal_table()`: Assist-Text-Aufteilung (Zeile 2302-2307)
  - `get_or_create_player()`: Assist-Text-Filterung (Zeile 642-645)
  - `get_or_create_team()`: Erweiterte Pattern-Erkennung (Zeile 487-510)

### Dokumentation
- `docs/PARSER_FIX_ASSIST_TEXTE.md`: Dokumentation der Assist-Text-Filterung
- `docs/REPARSE_RESULTS_FINAL.md`: Finale Auswertung des Re-Parses

## [2025-11] Data Cleansing & Parser Validation

### Neue Features
- **Data Cleansing Pipeline**: Umfassende Scripts zur Identifikation und Bereinigung von Datenfehlern
- **Parser-Validierung**: Automatische Filterung von ungültigen Spielernamen (Trainer, Schiedsrichter, Tor-Text)
- **Unicode-Unterstützung**: Korrekte Behandlung von Namen mit Akzenten (Á, É, etc.)
- **Fehlerbehandlung**: Robuste Fehlerbehandlung mit Logging statt Abbruch

### Scripts
- `data_cleansing/identify_and_document_errors.py`: Identifiziert problematische Einträge
- `data_cleansing/validate_against_html.py`: Validiert gegen HTML-Rohdaten
- `data_cleansing/analyze_parser_errors.py`: Analysiert Fehler und erstellt Verbesserungsplan
- `data_cleansing/clean_database.py`: Automatische Bereinigung

### Parser-Verbesserungen
- Validierung für Trainer-Namen, Schiedsrichter-Namen, Tor-Text
- Filterung von Fehlertext-Präfixen ("FE,", "ET,", "HE,")
- Unicode-Buchstaben-Validierung
- Längen-Validierung für Namen

### Geänderte Dateien
- `comprehensive_fsv_parser.py`: Validierungen und Fehlerbehandlung hinzugefügt
- `tests/test_improved_parser.py`: Test-Script für verbesserten Parser

### Dokumentation
- `data_cleansing/README.md`: Data-Cleansing-Dokumentation
- `data_cleansing/parser_improvements.md`: Parser-Verbesserungsplan

## [2025-01] Parser Improvements & Liga-Klassifizierung

### Neue Features
- **Dynamische Liga-Extraktion**: Liga-Namen werden jetzt automatisch aus HTML-Dateien extrahiert statt hardcodiert
- **Automatische Level-Bestimmung**: Competition-Level wird basierend auf Liga-Namen automatisch bestimmt
- **Erweiterte Europapokal-Erkennung**: `profirest.html` Dateien werden jetzt erkannt

### Fixes
- **Liga-Klassifizierung**: Alle historischen Ligen werden jetzt korrekt erkannt (Oberliga, Regionalliga, 2. Bundesliga, etc.)
- **Duplikat-Prävention**: Karten, Goals, Substitutions und Lineups werden dedupliziert
- **Transaction Management**: Verbesserte Fehlerbehandlung mit Transaktionen

### Geänderte Dateien
- `comprehensive_fsv_parser.py`: Liga-Extraktion und Level-Bestimmung integriert
- `prompts.yaml`: SQL-Prompts für neues Datenmodell aktualisiert

### Dokumentation
- `docs/PARSER_IMPROVEMENTS.md`: Vollständige Dokumentation der Parser-Verbesserungen
- `docs/PARSER_FIX_SUMMARY.md`: Zusammenfassung aller Fixes

## [2024-12] Performance Optimierungen

### Neue Features
- Materialized Views für schnelle Aggregationen
- Database Connection Pooling
- Performance Indexes

### Dokumentation
- `docs/PERFORMANCE_OPTIMIZATION.md`: Performance-Verbesserungen dokumentiert

## [2024-11] UI/UX Verbesserungen

### Neue Features
- Modernes Mainz 05 Branding
- Responsive Design
- Verbesserte Chat- und Quiz-Interfaces

### Geänderte Dateien
- `templates/index.html`: Komplett neues UI-Design

