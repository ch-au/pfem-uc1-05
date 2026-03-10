# Betrieb

## Standard-Workflow

### 1. HTML nach SQLite parsen

```bash
fsv-pipeline-parse
```

Lokalen Ordner explizit angeben:

```bash
fsv-pipeline-parse --source /path/to/fsvarchiv
```

Website-Spiegelmodus:

```bash
fsv-pipeline-parse --source https://example.com/fsvarchiv/
```

Optionaler Saisonfilter:

```bash
fsv-pipeline-parse --seasons 2023-24
```

Verhalten:

- liest das Archiv aus `--source`, wenn gesetzt, sonst aus `fsvarchiv/` oder `FSVARCHIV_PATH`
- spiegelt Website-Quellen vor dem Parsing in einen temporaeren lokalen Baum
- schreibt in die ueber `SQLITE_DB` konfigurierte SQLite-Datenbank
- baut die SQLite-Datenbank bei jedem Parse-Lauf neu auf

### 2. PostgreSQL-Sync als Vorschau

```bash
fsv-pipeline-sync --dry-run
```

Das sollte vor jedem manuellen Sync ausgefuehrt werden, um sicherzustellen, dass wirklich die gewuenschte lokale SQLite-Datenbank synchronisiert wird.

### 3. PostgreSQL-Sync ausfuehren

```bash
fsv-pipeline-sync
```

### 4. Verifizieren

```bash
fsv-pipeline-status
python -m unittest discover tests
```

## Optionale wiederholbare Aufgaben

### Profilindizes erzeugen

```bash
fsv-pipeline-build-indices
```

Ausgaben:
- `generated/indices/players.json`
- `generated/indices/coaches.json`
- `generated/indices/teams.json`
- `generated/indices/summary.json`

### Entity-Linking-Report erzeugen

```bash
fsv-pipeline-entity-report
```

Ausgaben:
- timestamped report in `generated/reports/`

## Sicherheitshinweise

- `fsv-pipeline-parse` ist destruktiv fuer die lokale SQLite-Datenbank, weil sie dabei neu aufgebaut wird.
- `fsv-pipeline-sync --dry-run` ist der empfohlene Preflight-Check.
- Historische Cleanup-, Wartungs- und Migrationsskripte gehoeren nicht zum unterstuetzten Betriebsmodell und sollten nicht als Standardpfad fuer aktuelle Arbeiten verwendet werden.
