# Database Migrations

## Overview

This directory contains SQL migration files for the FSV Mainz 05 database schema.

## Migration Files

### 001_existing_schema.sql
The original quiz_schema.sql (baseline schema with chat and quiz tables)

### 002_extend_schema_for_ts_app.sql
Extends the schema for the TypeScript application:
- Adds quiz_categories table
- Adds quiz_players table for player statistics
- Extends quiz_questions with AI tracing fields
- Extends quiz_games with game modes and categories
- Extends chat_messages with SQL query metadata
- Adds performance indices
- Adds triggers for automatic stat updates

**IMPORTANT**: This migration only ADDS new structures, it does NOT modify existing ones!

## Running Migrations

### Manual (using psql)

```bash
# Run specific migration
psql $DB_URL -f database/migrations/002_extend_schema_for_ts_app.sql

# Run all migrations in order
for f in database/migrations/*.sql; do
  echo "Running migration: $f"
  psql $DB_URL -f "$f"
done
```

### Programmatic (TypeScript)

```typescript
import { runMigrations } from './migrate';

await runMigrations();
```

## Schema Principles

1. **Never break existing schema** - Migrations only ADD, never modify or remove
2. **Use IF NOT EXISTS** - All migrations are idempotent
3. **Backwards compatible** - Old code continues to work
4. **Opt-in features** - New columns have defaults or NULL allowed
5. **Foreign keys with cascades** - Maintain referential integrity

## Testing Migrations

Before running in production:

1. Test on a copy of the production database
2. Verify all existing queries still work
3. Check performance with EXPLAIN ANALYZE
4. Test rollback strategy if needed
