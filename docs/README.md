# Documentation Index

This folder is the canonical home for current, reusable project documentation.

## Start Here

- `../README.md` - project overview and active repo layout
- `../fsv_data_pipeline/README.md` - maintained parser and sync workflow
- `DATABASE_SCHEMA.md` - PostgreSQL schema reference
- `CHATBOT_DESIGN.md` - app and chat architecture
- `BACKEND_IMPLEMENTATION.md` - API/backend notes

## Active Reference Docs

- `DATABASE_SCHEMA.md` - database schema and entities
- `MATERIALIZED_VIEWS_REFERENCE.md` - performance-oriented read models
- `SCHEMA_DOCUMENTATION_2025.md` - current schema-focused reference
- `SYNC_TO_POSTGRES.md` - SQLite -> PostgreSQL sync workflow
- `DATABASE_QUALITY_FINAL_REPORT.md` - latest durable quality summary
- `DATA_QUALITY_REPORT.md` - broader data-quality findings
- `DATA_QUALITY_BY_SEASON.md` - seasonal quality breakdown
- `DATA_QUALITY_FIX_PLAN.md` - current remediation plan
- `CHATBOT_DESIGN.md` - product and system design
- `BACKEND_IMPLEMENTATION.md` - backend implementation details
- `LLM_SQL_SCHEMA_REFERENCE.md` - schema guide for LLM/SQL work
- `CHANGELOG.md` - notable project changes

## Documentation Policy

- Keep evergreen reference docs in `docs/`.
- Remove or externalize dated reports, migration summaries, cleanup reports, and status snapshots instead of keeping them in active docs.
- Do not use the repo root for one-off markdown reports.
- Prefer one canonical document per topic and link to it from here.

## Local-Only Artifacts

The following paths are treated as local/generated working data rather than project documentation:

- `../backups/`
- `../parsing/indices/`
- `../parsing/reports/`
- `../attached_assets/`

If an artifact matters long-term, extract the durable findings into a doc here instead of committing the raw output.
