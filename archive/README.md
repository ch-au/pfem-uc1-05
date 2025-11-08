# Archiv - FSV Mainz 05 Projekt

**Erstellt:** 29. Oktober 2025  
**Zweck:** Sicherung alter/temporärer Dateien aus dem Entwicklungsprozess

## Verzeichnisstruktur

### migration/
Einmalig genutzte Migrations- und Sync-Scripts:
- Migration zur Neon Postgres Cloud
- Euro-Daten Synchronisation
- Duplikat-Entfernung
- Team-Konsolidierung

### debug/
Debug- und Test-Scripts aus der Entwicklung:
- Test-Scripts für Parser
- Debug-Ausgaben
- Datenbereinigung

### old_agents/
Alte Versionen der SQL-Agenten:
- simple_agent.py, improved_agent.py, enhanced_agent.py, sql_agent.py
- Ersetzt durch final_agent.py

### old_docs/
Überholte/Temporäre Dokumentation:
- Migrations-Reports
- Vergleichs-Dokumentationen
- Session-Summaries

### old_databases/
Alte SQLite-Datenbanken:
- Backup-Versionen
- Test-Datenbanken

### optimization/
Einmalig genutzte Optimierungs-Scripts:
- Performance-Analysen
- Schema-Upgrades

### temp_files/
Temporäre Dateien:
- SQL-Query-Fragmente
- Log-Dateien
- Cache-Dateien (66MB!)

## Wiederherstellen

Falls eine Datei benötigt wird:
```bash
cp archive/kategorie/datei.py .
```

## Löschen

Wenn sicher, dass Archiv nicht mehr benötigt wird:
```bash
rm -rf archive/
```
