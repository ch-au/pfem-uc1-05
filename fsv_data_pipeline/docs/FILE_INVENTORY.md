# Datei-Inventar

Das ist die explizite Keep-/Classify-Uebersicht fuer das aktive Paket `fsv_data_pipeline` nach der Oberflaechen-Bereinigung.

Legende:

- `core`: Day-One-Handover-Oberflaeche
- `supporting`: kleiner optionaler Helfer, der weiter zum Paket gehoert
- `test`: reproduzierbare Verifikation
- `reference`: verbindliche Dokumentation oder Konfiguration

Historisches Material gehoert nicht zur aktiven Paketoberflaeche.

## Root-Dateien

| Pfad | Status | Hinweis |
|------|--------|---------|
| `.env.example` | `reference` | Umgebungs-Template |
| `.gitignore` | `reference` | Ignore-Regeln, inklusive generierter Ausgaben |
| `README.md` | `core` | Paketuebersicht und unterstuetzter Workflow |
| `check_pg_status.py` | `core` | PostgreSQL-Statuscheck |
| `config.py` | `core` | Gemeinsamer Konfigurations-Loader |
| `pyproject.toml` | `core` | Installierbare Paketmetadaten und CLI-Einstiegspunkte |
| `requirements.txt` | `reference` | Kompatibilitaetsdatei fuer Editable-Installationen |

Nicht Teil der aktiven Oberflaeche:

- `generated/` als bewusst ignorierter Ausgabeort
- lokale Build-Artefakte wie `*.egg-info/`
- lokale Cache- oder Tool-Verzeichnisse wie `.ruff_cache/`, `.desloppify/` oder `.cursor/`

## Dokumentation

| Pfad | Status | Hinweis |
|------|--------|---------|
| `docs/ARCHITECTURE.md` | `reference` | Datenfluss und Paketverantwortung |
| `docs/DATABASE_SCHEMA.md` | `reference` | Aktuelle Schema-Fakten |
| `docs/FILE_INVENTORY.md` | `reference` | Keep-/Surface-Klassifikation |
| `docs/HANDOVER.md` | `reference` | Onboarding-Runbook fuer neue Maintainer |
| `docs/OPERATIONS.md` | `reference` | Wiederholbare Betriebsbefehle |

## Aktiver Parsing-Code

| Pfad | Status | Hinweis |
|------|--------|---------|
| `parsing/__init__.py` | `reference` | Paketmarker |
| `parsing/comprehensive_fsv_parser.py` | `core` | Kanonischer HTML-nach-SQLite-Parser |
| `parsing/database_manager.py` | `core` | SQLite-Schema, Persistenz und Batch-Insert-Logik |
| `parsing/entity_linking_report.py` | `supporting` | Optionaler Linking-Qualitaetsreport |
| `parsing/entity_linking_report_renderer.py` | `supporting` | Renderer fuer Linking-Report-Ausgaben |
| `parsing/html_utils.py` | `supporting` | Gemeinsame HTML- und Text-Helfer |
| `parsing/match_types.py` | `supporting` | Dataklassen fuer Parsing-Ergebnisse |
| `parsing/parser_match_helpers.py` | `supporting` | Wiederverwendbare Match-Parsing-Helfer |
| `parsing/parser_profile_enrichment.py` | `supporting` | Profilanreicherung fuer Spieler und Trainer |
| `parsing/profile_index_builder.py` | `supporting` | Optionale Erzeugung von Profilindizes |
| `parsing/profile_parsers.py` | `supporting` | Parser fuer Profilseiten |
| `parsing/source_preparation.py` | `supporting` | Vorbereitung lokaler oder gespiegelt geladener Quellen |

## Aktiver Datenbank-Code und SQL

| Pfad | Status | Hinweis |
|------|--------|---------|
| `database/__init__.py` | `reference` | Paketmarker |
| `database/001_create_schema.sql` | `core` | PostgreSQL-Basisschema |
| `database/002_materialized_views.sql` | `supporting` | Definitionen fuer Materialized Views |
| `database/sync_plan.py` | `supporting` | Sync-Planungslogik |
| `database/sync_sqlite_to_postgres.py` | `core` | Kanonischer SQLite-nach-Postgres-Sync |

## Datenbank-Migrationen

| Pfad | Status | Hinweis |
|------|--------|---------|
| `database/migrations/README.md` | `reference` | Hinweise zur Verwendung der Migrationen |
| `database/migrations/002_extend_schema_for_ts_app.sql` | `reference` | Schema-Erweiterung fuer die TypeScript-App |
| `database/migrations/003_performance_optimizations.sql` | `reference` | Performance-Migration |
| `database/migrations/003_performance_optimizations_corrected.sql` | `reference` | Korrigierte Performance-Migration |
| `database/migrations/004_add_unique_constraints.sql` | `reference` | Constraint-Migration |
| `database/migrations/005_add_team_foreign_keys.sql` | `reference` | Foreign-Key-Migration fuer Teams |
| `database/migrations/006_merge_duplicate_mainz_teams.sql` | `reference` | Konsolidierung doppelter Mainz-Teamdatensaetze |
| `database/migrations/007_create_materialized_views.sql` | `reference` | Migration fuer Materialized Views |
| `database/migrations/008_add_quiz_generation_jobs.sql` | `reference` | Migration fuer Quiz-Generierungsjobs |

## Tests

| Pfad | Status | Hinweis |
|------|--------|---------|
| `tests/test_helper_modules.py` | `test` | Unit-Tests fuer extrahierte Helfer und Parser-Bausteine |
| `tests/test_profile_entity_linking.py` | `test` | Unit- und optionale Integrationsabdeckung fuer Profil-Linking |
| `tests/test_smoke.py` | `test` | Reproduzierbare Smoke-Tests fuer Parser, Sync-CLI und Statusverhalten |
| `tests/fixtures/fsvarchiv/2010-11/profiliga.html` | `test` | Kleines Parser-Fixture-Archiv |

## Richtlinie fuer generierte Ausgaben

Generierte Artefakte werden bewusst nicht versioniert. Aktive Skripte schreiben sie unter:

- `generated/indices/`
- `generated/reports/`
- `generated/compare/`
