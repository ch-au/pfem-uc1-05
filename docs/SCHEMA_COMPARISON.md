# Schema Comparison: SQLite vs PostgreSQL

**Last Updated:** 2025-11-25  
**Purpose:** Document differences between SQLite (parser output) and PostgreSQL (production)

---

## 🎯 Summary

Both databases contain the **same core football data** but with different features:

- **SQLite**: Parser output, read-only, local development
- **PostgreSQL**: Production database with vector search, materialized views, and application tables

---

## 📊 Data Sync Status

### Core Tables (Football Data)

| Table | SQLite | PostgreSQL | Synced | Notes |
|-------|--------|------------|--------|-------|
| **teams** | 585 | 585 | ✅ 100% | Perfect match |
| **players** | 9,916 | 9,955 | ⚠️ 99.6% | +39 in PostgreSQL |
| **coaches** | 566 | 566 | ✅ 100% | Same count, names differ |
| **matches** | 3,956 | 3,956 | ✅ 100% | Including profirest |
| **goals** | 8,312 | 8,312 | ✅ 100% | Perfect match |
| **cards** | 5,768 | 5,768 | ✅ 100% | Perfect match |
| **substitutions** | 10,080 | ~10,029 | ✅ ~99% | Minor difference |
| **lineups** | 93,302 | ~91,475 | ✅ ~98% | Minor difference |

### Name Enrichment Status

| Metric | SQLite | PostgreSQL | Sync % |
|--------|--------|------------|--------|
| Players with full names | 1,910 (19.3%) | 1,669 (16.8%) | 87.4% |
| Coaches with full names | 77 (13.6%) | 22 (3.9%) | 28.6% |

**Action Required:** Sync remaining enriched names with `database/sync_now.py`

---

## 🔍 Schema Differences

### 1. Primary Key Names

**SQLite:** Uses descriptive names
```sql
-- SQLite
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
);
CREATE TABLE players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
);
CREATE TABLE matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
);
```

**PostgreSQL:** Uses generic `id`
```sql
-- PostgreSQL
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    ...
);
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    ...
);
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    ...
);
```

**Impact:** Requires ID mapping when syncing

---

### 2. Vector Embeddings (PostgreSQL Only)

```sql
-- PostgreSQL only
ALTER TABLE teams ADD COLUMN name_embedding vector(1024);
ALTER TABLE players ADD COLUMN name_embedding vector(1024);
```

**Purpose:** Semantic search with Cohere embed-v4.0
**Usage:** Fuzzy name matching, similarity searches

---

### 3. Materialized Views (PostgreSQL Only)

| View | Purpose | Refresh |
|------|---------|---------|
| `mainz_match_results` | Denormalized match data | Daily |
| `player_career_stats` | Aggregated player stats | Weekly |
| `season_performance` | Season summaries | Weekly |
| `competition_statistics` | Competition summaries | Monthly |

**Performance:** 100-400x faster than JOINs on raw tables

---

### 4. Application Tables (PostgreSQL Only)

#### Quiz Application
```sql
CREATE TABLE quiz_games (...);
CREATE TABLE quiz_questions (...);
CREATE TABLE quiz_rounds (...);
CREATE TABLE quiz_answers (...);
CREATE TABLE quiz_categories (...);
CREATE TABLE quiz_players (...);
```

**Current Data:**
- 69 quiz games
- 92 questions
- Active quiz functionality

#### Chat Application
```sql
CREATE TABLE chat_sessions (...);
CREATE TABLE chat_messages (...);
```

**Current Data:**
- 287 chat sessions
- 199 messages

---

### 5. Data Type Differences

| Column | SQLite | PostgreSQL |
|--------|--------|------------|
| Dates | `TEXT` | `DATE` |
| Timestamps | `TEXT` | `TIMESTAMP WITH TIME ZONE` |
| UUIDs | Not used | `UUID` (for quiz/chat) |
| Booleans | `INTEGER` (0/1) | `BOOLEAN` |

---

### 6. Constraints & Indexes

**PostgreSQL has enhanced constraints:**
```sql
-- Unique constraints to prevent duplicates (Migration 004)
CREATE UNIQUE INDEX idx_goals_unique_event 
ON goals (match_id, COALESCE(player_id, -1), minute, COALESCE(stoppage, 0));

CREATE UNIQUE INDEX idx_cards_unique_event 
ON cards (match_id, player_id, COALESCE(minute, -1), COALESCE(stoppage, 0), card_type);

CREATE UNIQUE INDEX idx_lineups_unique_entry 
ON match_lineups (match_id, player_id, team_id);
```

**PostgreSQL has 107 indexes** vs SQLite's basic indexes

---

## 🔄 Sync Architecture

### Current Approach

```
┌─────────────┐
│  HTML Files │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  Parser             │
│  (comprehensive_    │
│   fsv_parser.py)    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  SQLite             │    ◄── Source of Truth
│  (fsv_archive_      │        for match data
│   complete.db)      │
└──────┬──────────────┘
       │
       │ Sync Scripts:
       │ - sync_now.py (coaches)
       │ - CSV export/import
       │ - Manual SQL
       │
       ▼
┌─────────────────────┐
│  PostgreSQL (Neon)  │    ◄── Production
│  + Vector Search    │        + Quiz/Chat
│  + Materialized     │        + API
│    Views            │
│  + Application      │
│    Tables           │
└─────────────────────┘
```

### Sync Methods

1. **Coach Names** (Safe - uses normalized_name):
   ```bash
   python database/sync_now.py
   ```

2. **Core Data** (CSV export/import):
   ```bash
   sqlite3 fsv_archive_complete.db -csv -header 'SELECT * FROM matches' > matches.csv
   psql $DB_URL -c "\COPY matches FROM 'matches.csv' CSV HEADER"
   ```

3. **Full Sync** (Python with ID mapping):
   ```bash
   python database/final_postgres_sync.py --dry-run
   python database/final_postgres_sync.py
   ```

---

## 📋 Common Tables

These tables exist in both databases with same structure (except ID naming):

**Master Data:**
- `teams` - All teams (Mainz + opponents)
- `players` - Player master data
- `coaches` - Coach master data
- `referees` - Referee master data
- `competitions` - Competition definitions
- `seasons` - Season records

**Match Data:**
- `matches` - Match results
- `goals` - Goal events
- `cards` - Card events
- `match_lineups` - Player appearances
- `match_substitutions` - Substitution events
- `match_coaches` - Coach assignments
- `match_referees` - Referee assignments

**Additional:**
- `season_competitions` - Season-competition links
- `season_squads` - Squad assignments
- `player_careers` - Player career history
- `coach_careers` - Coach career history
- `season_matchdays` - Matchday standings
- `player_aliases` - Alternative player names (empty)
- `match_notes` - Match notes (empty)

---

## 🎯 Key Takeaways

### Use SQLite For:
- ✅ Parser output and development
- ✅ Local testing
- ✅ Match data verification
- ✅ Backup/export

### Use PostgreSQL For:
- ✅ Production API
- ✅ Quiz/chat applications
- ✅ Vector search (semantic matching)
- ✅ High-performance queries (materialized views)
- ✅ Multi-user access
- ✅ Cloud deployment

### Both Contain:
- ✅ Same match data (3,956 matches)
- ✅ Same goal/card/lineup events
- ✅ Same teams, players, coaches

### PostgreSQL Extra:
- ✅ Vector embeddings
- ✅ Materialized views
- ✅ Quiz/chat tables
- ✅ Advanced indexes
- ✅ Better data types

---

## 📞 Related Documentation

- **`SCHEMA_DOCUMENTATION_2025.md`** - Detailed PostgreSQL schema
- **`DATABASE_README.md`** - SQLite database overview
- **`SYNC_TO_POSTGRES.md`** - Sync procedures and status
- **`DATABASE_SYNC_STATUS_FINAL.md`** - Complete sync status report

---

**Last Verified:** 2025-11-25  
**Verification Tool:** `check_pg_status.py`

