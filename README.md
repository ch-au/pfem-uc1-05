# FSV Mainz 05 Archive

Monorepo fuer die Abfrage von 120 Jahren FSV-Mainz-05-Geschichte mit React-Frontend, Fastify-API und einer Python-Datenpipeline.

## Aktive Bestandteile

- `apps/api/` - aktives TypeScript/Fastify-Backend
- `frontend/` - React-19-Frontend mit Vite
- `fsv_data_pipeline/` - gepflegte Python-Pipeline fuer `HTML -> SQLite -> PostgreSQL`
- `docs/` - aktuelle Projektdokumentation
- `archive/` - bewusst ausgelagertes historisches Material ausserhalb des aktiven Workflows

Das alte Python-Backend in `backend/` bleibt nur als Referenz erhalten und ist nicht der primaere App-Backend-Pfad.

## Schnellstart

```bash
pnpm install
cp .env.example .env
pnpm dev
```

Nuetzliche Entwicklungsbefehle:

```bash
pnpm dev:api
pnpm dev:web
pnpm build
pnpm run typecheck
```

Verwende fuer die App bewusst nur diese `pnpm`-Workflows. Veraltete Root-Startskripte und Replit-spezifische Wrapper gehoeren nicht mehr zum unterstuetzten Setup.

## Datenpipeline

Fuer den gepflegten Parser-/Sync-Workflow ist `fsv_data_pipeline/` der relevante Einstiegspunkt:

```bash
cd fsv_data_pipeline
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
fsv-pipeline-parse
fsv-pipeline-sync --dry-run
```

Das rohe HTML-Archiv liegt in `fsvarchiv/` und ist absichtlich nicht versioniert.

## Dokumentation

Starte mit `docs/README.md`.

Empfohlene Einstiegspunkte:

- `docs/README.md` - Doku-Index und Bereinigungsregeln
- `docs/DATABASE_SCHEMA.md` - Referenz fuer das PostgreSQL-Schema
- `docs/CHATBOT_DESIGN.md` - Architektur von App und Chat
- `fsv_data_pipeline/README.md` - gepflegter Parsing- und Sync-Workflow

## Repo-Konventionen

- Dauerhaft relevante Referenzdokumente gehoeren nach `docs/`.
- Historische Reports und Einmal-Snapshots gehoeren nach `archive/`.
- Lokale Dumps, generierte Reports, Indizes und Capture-Artefakte bleiben aus Git heraus, sofern sie keine bewussten Projekt-Assets sind.
