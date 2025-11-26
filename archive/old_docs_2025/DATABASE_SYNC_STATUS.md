# Database Sync Status Report

**Generated:** 2025-11-25  
**Purpose:** Address database sync and schema documentation issues

---

## 🔍 Issue Summary

### Question 1: Are latest extracted results synced with PostgreSQL?

**Answer: ⚠️ NO - Sync is incomplete**

### Question 2: Is the correct schema in documentation?

**Answer: ⚠️ PARTIALLY - Multiple schema documents exist with inconsistencies**

---

## 📊 Current Database State

### SQLite (Local - Source of Truth)

**File:** `fsv_archive_complete.db` (4.5 MB)

| Metric | Count | Status |
|--------|-------|--------|
| **Matches** | 3,956 | ✅ Complete |
| **Players** | 9,916 | ✅ Complete |
| **Players with Full Names** | 1,910 (19.3%) | ✅ Enriched |
| **Coaches** | 566 | ✅ Complete |
| **Coaches with Full Names** | 77 (13.6%) | ✅ Enriched |
| **Teams** | 585 | ✅ Complete |
| **Profirest Matches** | 668 | ✅ Parsed & Stored |
| **Goals** | 8,312 | ✅ Complete |
| **Cards** | 5,768 | ✅ Complete |
| **Substitutions** | 10,080 | ✅ Complete |
| **Lineups** | 93,302 | ✅ Complete |

**Last Updated:** November 10, 2025 (Profirest integration)

#### SQLite Schema

```sql
-- Core tables
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    normalized_name TEXT UNIQUE,
    team_type TEXT,
    profile_url TEXT
);

CREATE TABLE players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    normalized_name TEXT UNIQUE,
    birth_date TEXT,
    birth_place TEXT,
    height_cm INTEGER,
    weight_kg INTEGER,
    primary_position TEXT,
    nationality TEXT,
    profile_url TEXT,
    image_url TEXT
);

CREATE TABLE matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_competition_id INTEGER,
    round_name TEXT,
    matchday INTEGER,
    leg INTEGER,
    match_date TEXT,
    kickoff_time TEXT,
    venue TEXT,
    attendance INTEGER,
    referee_id INTEGER,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score INTEGER,
    away_score INTEGER,
    halftime_home INTEGER,
    halftime_away INTEGER,
    extra_time_home INTEGER,
    extra_time_away INTEGER,
    penalties_home INTEGER,
    penalties_away INTEGER,
    source_file TEXT,
    UNIQUE (season_competition_id, source_file),
    FOREIGN KEY (season_competition_id) REFERENCES season_competitions(season_competition_id),
    FOREIGN KEY (referee_id) REFERENCES referees(referee_id),
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
);

-- Additional tables: coaches, referees, competitions, seasons, 
-- season_competitions, goals, cards, match_lineups, match_substitutions,
-- match_coaches, match_referees, player_careers, coach_careers,
-- season_squads, player_aliases, match_notes, season_matchdays
```

---

### PostgreSQL (Neon - Production)

**Connection:** Via `DB_URL` environment variable  
**Status:** ⚠️ **Out of Sync**

#### Known Issues:

1. **Missing Profirest Matches**
   - 668 profirest matches (historical 1905-1960s) are in SQLite
   - These are NOT yet synced to PostgreSQL
   - Represents 16.9% of total match data

2. **Coach Names Not Updated**
   - SQLite has 77 coaches with full names (enriched)
   - PostgreSQL likely has old abbreviated names

3. **Schema Differences**
   - SQLite uses `player_id`, `team_id`, `match_id` (INTEGER AUTOINCREMENT)
   - PostgreSQL uses `id` (SERIAL PRIMARY KEY)
   - Column naming inconsistency requires ID mapping

4. **PostgreSQL Extended Schema**
   - PostgreSQL has additional features not in SQLite:
     - `name_embedding vector(1024)` for semantic search
     - Quiz tables (quiz_games, quiz_questions, quiz_rounds, quiz_answers)
     - Chat tables (chat_sessions, chat_messages)
     - Materialized views for performance
     - Extended columns in quiz tables (categories, langfuse tracking)

#### PostgreSQL Exclusive Tables

```sql
-- Quiz Application
CREATE TABLE quiz_games (...);
CREATE TABLE quiz_questions (...);
CREATE TABLE quiz_rounds (...);
CREATE TABLE quiz_answers (...);
CREATE TABLE quiz_categories (...);
CREATE TABLE quiz_players (...);

-- Chat Application
CREATE TABLE chat_sessions (...);
CREATE TABLE chat_messages (...);

-- Performance Views
CREATE MATERIALIZED VIEW mainz_match_results (...);
CREATE MATERIALIZED VIEW player_career_stats (...);
CREATE MATERIALIZED VIEW season_performance (...);
CREATE MATERIALIZED VIEW competition_statistics (...);
```

---

## 📚 Schema Documentation Status

### Existing Documentation Files

| File | Status | Issues |
|------|--------|--------|
| `docs/SCHEMA_DOCUMENTATION_2025.md` | ⚠️ Outdated | Says 3,956 matches but doesn't clarify sync status |
| `docs/SCHEMA_DOCUMENTATION.md` | ⚠️ Old | Shows 3,231 matches (pre-profirest) |
| `docs/SYNC_TO_POSTGRES.md` | ⚠️ Incomplete | Lists sync as "Not yet implemented" |
| `DATABASE_README.md` | ✅ Good | Accurately describes SQLite state |
| `database/quiz_schema.sql` | ✅ Good | Quiz/chat tables only |
| `database/migrations/*.sql` | ✅ Good | PostgreSQL-specific migrations |

### Documentation Inconsistencies

1. **Match Counts Vary**
   - `SCHEMA_DOCUMENTATION.md`: 3,231 matches (October 2025)
   - `SCHEMA_DOCUMENTATION_2025.md`: 3,956 matches (November 2025)
   - `DATABASE_README.md`: 3,956 matches ✅ (Correct)
   - **Reality (SQLite):** 3,956 matches ✅

2. **Schema Format**
   - `SCHEMA_DOCUMENTATION_2025.md` shows PostgreSQL schema (with `team_id`)
   - But lists features that may not be synced (profirest matches, embeddings)

3. **Sync Status Unclear**
   - No clear documentation of what IS synced vs what ISN'T
   - No date of last PostgreSQL sync

---

## 🔄 Sync Scripts Status

### Available Scripts

1. **`database/sync_to_postgres.py`** ⚠️ Template Only
   - Has basic structure
   - Only syncs teams and players
   - Missing: coaches, matches, lineups, goals, cards, subs
   - No ID mapping between SQLite and PostgreSQL

2. **`database/final_postgres_sync.py`** ⚠️ Incomplete
   - More complete than sync_to_postgres.py
   - Has all sync methods defined
   - Most methods return "Skipped (implement if needed)"
   - Only teams and players partially implemented

3. **`database/sync_now.py`** ⚠️ Manual Only
   - Can update coach names (safe with normalized_name)
   - Cannot sync profirest matches (no team ID mapping)
   - Recommends manual CSV export/import

4. **`database/sync_complete.sh`** ⚠️ Export Only
   - Exports SQLite to SQL dump
   - Attempts SQL conversion (incomplete)
   - Ends with "MANUAL SYNC REQUIRED" message

### Why Sync is Hard

**ID Mapping Problem:**
- SQLite `team_id=1` might not be PostgreSQL `id=1`
- SQLite `player_id=123` might be PostgreSQL `id=456`
- Matches reference teams/players by ID
- Need to build complete ID mapping table first

**Schema Differences:**
```
SQLite                    PostgreSQL
-------                   ----------
team_id (int)      →      id (serial)
player_id (int)    →      id (serial)
                          + name_embedding vector(1024)
                          + quiz/chat tables
```

---

## 🎯 Recommendations

### 1. Clarify Sync Strategy

Choose one of:

**Option A: PostgreSQL as Production (Recommended)**
- Keep SQLite as parser output only
- Sync all SQLite data to PostgreSQL
- Use PostgreSQL for API/app
- Benefits: Vector search, materialized views, proper transactions

**Option B: Dual Database**
- Keep SQLite for historical/read-only data
- Use PostgreSQL only for quiz/chat features
- Accept data duplication
- Benefits: Simpler sync (quiz data only)

### 2. Complete the Sync (Option A)

**Steps:**

```bash
# 1. Build ID mapping
python database/build_id_mapping.py --dry-run
# Creates: team_id_map, player_id_map, coach_id_map, etc.

# 2. Sync core entities (teams, players, coaches)
python database/sync_entities.py --dry-run
python database/sync_entities.py

# 3. Sync matches with mapped team IDs
python database/sync_matches.py --dry-run
python database/sync_matches.py

# 4. Sync match events (lineups, goals, cards, subs) with mapped IDs
python database/sync_events.py --dry-run
python database/sync_events.py

# 5. Verify sync
python database/verify_sync.py
```

**Or use manual CSV approach:**

```bash
# Export tables
sqlite3 fsv_archive_complete.db -csv -header 'SELECT * FROM teams' > teams.csv
sqlite3 fsv_archive_complete.db -csv -header 'SELECT * FROM players' > players.csv
# ... repeat for all tables

# Manually adjust IDs in CSV files to match PostgreSQL

# Import to PostgreSQL
psql $DB_URL -c "\COPY teams FROM 'teams.csv' CSV HEADER"
psql $DB_URL -c "\COPY players FROM 'players.csv' CSV HEADER"
# ... repeat for all tables
```

### 3. Consolidate Documentation

**Create single source of truth:**

1. **Archive `SCHEMA_DOCUMENTATION.md`** (October 2025 version)
   - Move to `archive/old_docs/`

2. **Update `SCHEMA_DOCUMENTATION_2025.md`**
   - Add clear sync status section
   - Specify "SQLite Schema" vs "PostgreSQL Schema"
   - Add "Last Synced" timestamp
   - List what's in SQLite but NOT in PostgreSQL

3. **Update `SYNC_TO_POSTGRES.md`**
   - Add actual sync instructions
   - Document ID mapping process
   - Include verification queries
   - Add "Last Sync: [date]" section

4. **Create `docs/SCHEMA_UNIFIED.md`** (new)
   - Combined view of both databases
   - Clear indication of differences
   - Sync status table
   - Migration path

### 4. Verification Queries

After sync, run these to verify:

```sql
-- PostgreSQL
SELECT COUNT(*) FROM matches; -- Should be 3956
SELECT COUNT(*) FROM matches WHERE source_file LIKE '%profirest%'; -- Should be 668
SELECT COUNT(*) FROM players WHERE name LIKE '% %'; -- Should be 1910
SELECT COUNT(*) FROM coaches WHERE name LIKE '% %'; -- Should be 77

-- Check Jürgen Klopp
SELECT name, birth_date, birth_place FROM coaches WHERE normalized_name LIKE '%klopp%';
-- Should return: "JÜRGEN KLOPP", 1967-06-16, Stuttgart

-- Check team consolidation
SELECT COUNT(*) FROM teams WHERE normalized_name = 'fsv mainz 05';
-- Should be 1 (team_id/id = 1)
```

---

## 📋 Action Items

### High Priority
- [ ] Decide on sync strategy (Option A or B)
- [ ] Build complete ID mapping script
- [ ] Sync profirest matches (668 missing)
- [ ] Sync enriched coach names (77 records)
- [ ] Update `SCHEMA_DOCUMENTATION_2025.md` with sync status
- [ ] Archive outdated `SCHEMA_DOCUMENTATION.md`

### Medium Priority
- [ ] Create verification queries
- [ ] Document sync process in `SYNC_TO_POSTGRES.md`
- [ ] Add "Last Synced" timestamps to docs
- [ ] Create unified schema documentation

### Low Priority
- [ ] Automate sync with cron job
- [ ] Add sync status dashboard
- [ ] Monitor PostgreSQL vs SQLite data divergence

---

## 🔗 Related Files

- SQLite Database: `fsv_archive_complete.db`
- Backups: `database/backups/`
- Sync Scripts: `database/sync_*.py`, `database/final_postgres_sync.py`
- Documentation: `docs/SCHEMA_*.md`, `DATABASE_README.md`
- Migrations: `database/migrations/*.sql`
- Schema Files: `database/quiz_schema.sql`

---

## 📞 Next Steps

1. **Test PostgreSQL connection:**
   ```bash
   psql $DB_URL -c "SELECT COUNT(*) FROM matches;"
   ```

2. **Compare counts:**
   ```bash
   # SQLite
   sqlite3 fsv_archive_complete.db "SELECT COUNT(*) FROM matches;"
   
   # PostgreSQL
   psql $DB_URL -c "SELECT COUNT(*) FROM matches;"
   ```

3. **Identify missing data:**
   ```bash
   # Check profirest in PostgreSQL
   psql $DB_URL -c "SELECT COUNT(*) FROM matches WHERE source_file LIKE '%profirest%';"
   ```

4. **Choose sync method and proceed**

---

**End of Report**

