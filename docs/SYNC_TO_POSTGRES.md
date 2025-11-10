# Syncing SQLite Archive to PostgreSQL (Neon)

## Overview

The FSV Mainz 05 archive is parsed into a local SQLite database (`fsv_archive_complete.db`) which then needs to be synced to the production PostgreSQL database on Neon.

## Database Files

- **`fsv_archive_complete.db`** (4.5 MB) - Current complete database with profirest matches
- **`fsv_archive_complete_BEFORE_PROFIREST.db`** (3.1 MB) - Backup before profirest implementation

## Current Status

✅ **SQLite Database**: Complete and up-to-date
- 3,956 matches (including 668 profirest matches)
- 9,916 players (1,910 with full names)
- 585 teams
- 566 coaches

⚠️ **PostgreSQL Sync**: Not yet implemented
- The sync script at `database/sync_to_postgres.py` is a template
- Schema differences between SQLite and PostgreSQL need to be resolved
- Manual sync recommended for now

## Manual Sync Process

### Option 1: Using existing migration scripts

Check the `archive/migration/` directory for existing sync scripts:
```bash
ls archive/migration/*.py
```

These scripts were used for previous Euro match syncs and can be adapted.

### Option 2: Export/Import via CSV

```bash
# Export from SQLite
sqlite3 fsv_archive_complete.db <<EOF
.headers on
.mode csv
.output matches.csv
SELECT * FROM matches WHERE source_file LIKE '%profirest%';
.quit
EOF

# Import to PostgreSQL
export DATABASE_URL="postgresql://neondb_owner:***@ep-steep-voice-a9u47j2b-pooler.gwc.azure.neon.tech/neondb?sslmode=require"
psql $DATABASE_URL -c "\COPY matches FROM 'matches.csv' CSV HEADER"
```

### Option 3: Direct SQL dump

```bash
# Create SQL dump of new data
sqlite3 fsv_archive_complete.db .dump > archive_dump.sql

# Edit dump to be PostgreSQL-compatible
# (Replace AUTOINCREMENT with SERIAL, adjust data types, etc.)

# Import to PostgreSQL
psql $DATABASE_URL -f archive_dump_postgres.sql
```

## Schema Mapping

### Teams Table
| SQLite | PostgreSQL | Notes |
|--------|------------|-------|
| `team_id` | `id` | Primary key |
| `name` | `name` | Team name |
| `normalized_name` | `normalized_name` | For matching |
| `team_type` | `team_type` | club/national |
| `profile_url` | `profile_url` | Link to archive |

### Players Table
| SQLite | PostgreSQL | Notes |
|--------|------------|-------|
| `player_id` | `id` | Primary key |
| `name` | `name` | Full name (e.g., "JÜRGEN KLOPP") |
| `normalized_name` | `normalized_name` | For matching |
| `profile_url` | `profile_url` | spieler/*.html |
| `date_of_birth` | `date_of_birth` | ISO format |
| `place_of_birth` | `place_of_birth` | Text |
| `nationality` | `nationality` | Country code |
| `position` | `position` | Player position |

### Matches Table
| SQLite | PostgreSQL | Notes |
|--------|------------|-------|
| `match_id` | `id` | Primary key |
| `match_date` | `match_date` | ISO format YYYY-MM-DD |
| `home_team_id` | `home_team_id` | FK to teams |
| `away_team_id` | `away_team_id` | FK to teams |
| `home_score` | `home_score` | Final score |
| `away_score` | `away_score` | Final score |
| `halftime_home` | `halftime_home` | Halftime score |
| `halftime_away` | `halftime_away` | Halftime score |
| `source_file` | `source_file` | Unique identifier |
| `attendance` | `attendance` | Number of spectators |
| `kickoff_time` | `kickoff_time` | Match time |

## Recommended Approach

1. **Verify PostgreSQL schema matches SQLite**
   ```bash
   psql $DATABASE_URL -c "\d teams"
   sqlite3 fsv_archive_complete.db ".schema teams"
   ```

2. **Test sync with dry-run**
   ```bash
   python database/sync_to_postgres.py --dry-run
   ```

3. **Fix schema mismatches** in the sync script

4. **Run actual sync**
   ```bash
   python database/sync_to_postgres.py
   ```

5. **Validate sync**
   ```bash
   # Check Klopp in PostgreSQL
   psql $DATABASE_URL -c "SELECT name, COUNT(*) FROM players p JOIN match_lineups ml ON p.id = ml.player_id WHERE name LIKE '%Klopp%' GROUP BY name;"
   ```

## Important Notes

- **Incremental sync**: Use `source_file` as unique identifier to avoid duplicates
- **ID mapping**: SQLite IDs won't match PostgreSQL - create mapping tables
- **Foreign keys**: Ensure all referenced teams/players exist before inserting matches
- **Transactions**: Wrap sync in transactions for rollback capability
- **Backup first**: Always backup PostgreSQL database before sync

## Next Steps

1. ✅ SQLite database complete with profirest matches
2. ⏳ Resolve PostgreSQL schema differences
3. ⏳ Complete sync_to_postgres.py implementation
4. ⏳ Test sync with subset of data
5. ⏳ Run full sync to production

## Support

For PostgreSQL connection issues:
- Check `DATABASE_URL` environment variable
- Verify Neon database is accessible
- Confirm SSL mode is set to `require`
