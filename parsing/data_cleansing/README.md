# Data Cleansing - Zusammenfassung

## Übersicht

Dieses Verzeichnis enthält Scripts zur Identifikation, Validierung und Bereinigung von Datenfehlern in der FSV Mainz 05 Datenbank.

## Scripts

### 1. `identify_and_document_errors.py`
Identifiziert problematische Einträge in Players, Teams, Coaches, Referees und dokumentiert jeden Fehler mit Quelle und Kontext.

**Verwendung:**
```bash
python data_cleansing/identify_and_document_errors.py
```

**Ausgabe:**
- `identified_errors.json` - Vollständige Fehlerliste
- `identified_errors_summary.json` - Zusammenfassung

### 2. `validate_against_html.py`
Validiert dokumentierte Fehler gegen HTML-Rohdaten und extrahiert korrekte Namen.

**Verwendung:**
```bash
python data_cleansing/validate_against_html.py
```

**Ausgabe:**
- `validated_errors.json` - Validierte Fehler mit korrekten Namen

### 3. `analyze_parser_errors.py`
Analysiert dokumentierte Fehler und erstellt einen Parser-Verbesserungsplan.

**Verwendung:**
```bash
python data_cleansing/analyze_parser_errors.py
```

**Ausgabe:**
- `error_analysis.json` - Fehleranalyse
- `parser_improvements.md` - Markdown-Report mit Verbesserungsplan

### 4. `clean_database.py`
Bereinigt Datenbank basierend auf dokumentierten Fehlern.

**Verwendung:**
```bash
# Dry-Run (zeigt was gemacht würde)
python data_cleansing/clean_database.py

# Live (führt Bereinigung durch)
python data_cleansing/clean_database.py --execute
```

**Ausgabe:**
- `cleaning_report.json` - Report der durchgeführten Bereinigungen

## Workflow

1. **Fehler identifizieren**: `identify_and_document_errors.py`
2. **Gegen HTML validieren**: `validate_against_html.py`
3. **Analysieren**: `analyze_parser_errors.py`
4. **Bereinigen** (optional): `clean_database.py --execute`

## Ergebnisse

- **1,056 Fehler identifiziert** (Players: 1,024, Referees: 3, Teams: 24, Coaches: 5)
- **680 korrekte Namen extrahiert** aus HTML
- **620 Parsing-Fehler bestätigt**
- **7 Parser-Verbesserungen** identifiziert und implementiert

## Parser-Verbesserungen

Alle identifizierten Probleme wurden im Haupt-Parser (`comprehensive_fsv_parser.py`) behoben:

- ✅ Trainer-Namen Filterung
- ✅ Schiedsrichter-Namen Filterung
- ✅ Tor-Text Filterung
- ✅ Fehlertext-Präfixe Filterung
- ✅ Unicode-Unterstützung
- ✅ Längen-Validierung

Siehe `parser_improvements.md` für Details.
