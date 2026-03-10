# Handover-Runbook

## Checkliste fuer neue Kollegen

1. Virtuelle Umgebung erstellen und aktivieren.
2. Paket mit `python -m pip install -e .` installieren.
3. `.env.example` nach `.env` kopieren.
4. `DATABASE_URL` oder `DB_URL` setzen.
5. Festlegen, ob der Parser aus einem lokalen Archivordner oder ueber eine per `--source` gespiegelte Website liest.
6. Parser ausfuehren.
7. Sync zuerst im Modus `--dry-run` starten.
8. Danach den echten Sync ausfuehren.
9. Mit `fsv-pipeline-status` pruefen.
10. `python -m unittest discover tests` ausfuehren.

## Unterstuetzte Befehle

| Befehl | Zweck | Eingaben | Ausgabe | Sicher erneut ausfuehrbar |
|--------|-------|----------|---------|---------------------------|
| `fsv-pipeline-parse` | HTML-Archiv nach SQLite parsen | lokaler Archivordner, Website-URL via `--source` oder Fallback auf `fsvarchiv/` / `FSVARCHIV_PATH` | SQLite-Datenbank | Ja, aber die SQLite-DB wird neu aufgebaut |
| `fsv-pipeline-sync --dry-run` | SQLite-nach-Postgres-Sync vorschauen | SQLite-DB + Postgres-URL | Konsolen-Zusammenfassung | Ja |
| `fsv-pipeline-sync` | SQLite-nach-Postgres-Sync ausfuehren | SQLite-DB + Postgres-URL | PostgreSQL-Daten | Soll wiederholbar sein |
| `fsv-pipeline-status` | PostgreSQL gegen SQLite vergleichen | SQLite-DB + Postgres-URL | Konsolen-Zusammenfassung | Ja |
| `fsv-pipeline-build-indices` | Optionale Profilindizes erzeugen | HTML-Profilverzeichnisse im Archiv | `generated/indices/` | Ja |
| `fsv-pipeline-entity-report` | Optionalen Linking-Report erzeugen | SQLite-DB + Indizes | `generated/reports/` | Ja |

## Unterstuetztes Betriebsmodell

- Primaerer Workflow: `HTML -> SQLite -> PostgreSQL`
- Primaerer Parser: `parsing/comprehensive_fsv_parser.py`
- Primaerer Sync: `database/sync_sqlite_to_postgres.py`

## Historisches Material

Historische Einmal-Skripte, ueberholte Dokus und Debug-Helfer gehoeren nicht zum unterstuetzten Betriebsmodell dieses Pakets.

## Hauefige Fehlerbilder

- Fehlender Archivpfad: Parser scheitert, weil weder `--source` noch `fsvarchiv/` / `FSVARCHIV_PATH` auf ein gueltiges Archiv zeigen.
- Unvollstaendige Website-Spiegelung: Parser scheitert, weil die angegebene URL nicht dieselbe HTML-Struktur wie das Archiv liefert.
- Fehlende Datenbank-URL: Sync- und Status-Befehle koennen nicht mit PostgreSQL verbinden.
- Leeres `generated/`-Verzeichnis: normal; es wird bei Bedarf erzeugt und ist absichtlich nicht versioniert.

## Eskalationsregel

Wenn eine Aufgabe auf entfernte Altpfade oder historische Einmal-Skripte verweist, behandle sie als Migrations- oder Bereinigungsfall und dokumentiere die Entscheidung vor dem Weiterarbeiten.
