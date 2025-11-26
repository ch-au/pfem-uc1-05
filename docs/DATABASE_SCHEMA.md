# FSV Mainz 05 Archive - Database Schema

**Database:** PostgreSQL 17 (Neon Cloud)
**Last Updated:** 2025-11-26
**Status:** Production Ready

---

## Quick Stats

| Metric | Count |
|--------|-------|
| **Total Tables** | 22 |
| **Materialized Views** | 4 |
| **Matches** | 3,956 |
| **Players** | 9,916 |
| **Coaches** | 566 |
| **Teams** | 585 |
| **Goals** | 8,312 |
| **Cards** | 5,768 |
| **Lineups** | 93,302 |
| **Embeddings** | 11,067 |

---

## Table Overview

### Core Entity Tables

| Table | Records | Description |
|-------|---------|-------------|
| `teams` | 585 | All teams (FSV Mainz + opponents) |
| `players` | 9,916 | Player master data |
| `coaches` | 566 | Coach master data |
| `referees` | 870 | Referee master data |
| `competitions` | 24 | Competition types (Bundesliga, DFB-Pokal, etc.) |
| `seasons` | 121 | Seasons from 1905-2025 |

### Match Data Tables

| Table | Records | Description |
|-------|---------|-------------|
| `matches` | 3,956 | All match records |
| `match_lineups` | 93,302 | Player appearances per match |
| `match_substitutions` | 10,080 | Substitution events |
| `goals` | 8,312 | Goal events with scorers/assists |
| `cards` | 5,768 | Yellow/red card events |
| `match_coaches` | 5,023 | Coach assignments per match |
| `match_referees` | 2,879 | Referee assignments |
| `match_notes` | - | Additional match notes |

### Relationship Tables

| Table | Records | Description |
|-------|---------|-------------|
| `season_competitions` | 264 | Season-competition mappings |
| `season_squads` | 434 | Squad rosters per season |
| `player_careers` | 1,817 | Player career history |
| `coach_careers` | 586 | Coach career history |
| `player_aliases` | - | Alternative player names |
| `season_matchdays` | 1,775 | League table progression |

### Application Tables

| Table | Records | Description |
|-------|---------|-------------|
| `chat_sessions` | - | Chat session management |
| `chat_messages` | - | Chat message storage |

---

## Schema Details

### teams
```sql
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    team_type TEXT,
    profile_url TEXT,
    name_embedding vector(1536)  -- Cohere embedding for semantic search
);
```

### players
```sql
CREATE TABLE players (
    player_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    birth_date TEXT,
    birth_place TEXT,
    height_cm INTEGER,
    weight_kg INTEGER,
    primary_position TEXT,
    nationality TEXT,
    profile_url TEXT,
    image_url TEXT,
    name_embedding vector(1536)
);
```

### coaches
```sql
CREATE TABLE coaches (
    coach_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    birth_date TEXT,
    birth_place TEXT,
    nationality TEXT,
    profile_url TEXT,
    name_embedding vector(1536)
);
```

### matches
```sql
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    season_competition_id INTEGER REFERENCES season_competitions,
    round_name TEXT,
    matchday INTEGER,
    leg INTEGER,
    match_date TEXT,
    kickoff_time TEXT,
    venue TEXT,
    attendance INTEGER,
    referee_id INTEGER REFERENCES referees,
    home_team_id INTEGER REFERENCES teams,
    away_team_id INTEGER REFERENCES teams,
    home_score INTEGER,
    away_score INTEGER,
    halftime_home INTEGER,
    halftime_away INTEGER,
    extra_time_home INTEGER,
    extra_time_away INTEGER,
    penalties_home INTEGER,
    penalties_away INTEGER,
    source_file TEXT,
    UNIQUE (season_competition_id, source_file)
);
```

### match_lineups
```sql
CREATE TABLE match_lineups (
    lineup_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches,
    team_id INTEGER REFERENCES teams,
    player_id INTEGER REFERENCES players,
    shirt_number INTEGER,
    is_starter INTEGER,
    minute_on INTEGER,
    stoppage_on INTEGER,
    minute_off INTEGER,
    stoppage_off INTEGER
);
```

### goals
```sql
CREATE TABLE goals (
    goal_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches,
    team_id INTEGER REFERENCES teams,
    player_id INTEGER REFERENCES players,
    assist_player_id INTEGER REFERENCES players,
    minute INTEGER,
    stoppage INTEGER,
    score_home INTEGER,
    score_away INTEGER,
    event_type TEXT  -- 'goal', 'penalty', 'own_goal'
);
```

### cards
```sql
CREATE TABLE cards (
    card_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches,
    team_id INTEGER REFERENCES teams,
    player_id INTEGER REFERENCES players,
    minute INTEGER,
    stoppage INTEGER,
    card_type TEXT  -- 'yellow', 'red', 'second_yellow'
);
```

### chat_sessions
```sql
CREATE TABLE chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour'),
    metadata JSONB
);
```

### chat_messages
```sql
CREATE TABLE chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    langfuse_trace_id TEXT,
    sql_query TEXT,
    sql_execution_time_ms INTEGER,
    sql_result_count INTEGER,
    confidence_score NUMERIC(5, 2),
    visualization_type TEXT
);
```

---

## Materialized Views

Pre-computed views for fast queries (100-400x speedup):

### mv_player_career_stats
Player career statistics with wins, draws, losses, goals, assists, cards.
```sql
-- Columns: player_id, name, normalized_name, birth_date, total_matches,
--          wins, draws, losses, goals, assists, yellow_cards, red_cards,
--          first_match, last_match

SELECT name, total_matches, wins, goals, assists
FROM mv_player_career_stats
WHERE normalized_name LIKE '%klopp%';

-- Result: JÜRGEN KLOPP | 431 | 181 | 62 | 33
```

### mv_team_stats
Team aggregate statistics.
```sql
-- Columns: team_id, name, normalized_name, total_matches, wins, draws,
--          losses, goals_for, goals_against, first_match, last_match

SELECT name, total_matches, wins, losses
FROM mv_team_stats
ORDER BY total_matches DESC LIMIT 10;
```

### mv_season_summary
Season/competition summaries.
```sql
-- Columns: season_id, season, competition, competition_level, matches_played,
--          home_wins, away_wins, draws, total_goals, season_start, season_end

SELECT season, competition, matches_played, total_goals
FROM mv_season_summary
WHERE competition = 'Bundesliga'
ORDER BY season DESC;
```

### mv_coach_record
Coach win/loss records.
```sql
-- Columns: coach_id, name, normalized_name, birth_date, total_matches,
--          wins, draws, losses, first_match, last_match

SELECT name, total_matches, wins, losses
FROM mv_coach_record
ORDER BY total_matches DESC LIMIT 10;
```

**Refresh all views:**
```sql
SELECT refresh_all_materialized_views();
-- Or individually:
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_career_stats;
```

---

## Vector Search (Embeddings)

All players, teams, and coaches have Cohere embeddings (1536 dimensions) for semantic search.

**Example: Find players similar to "Klopp"**
```sql
SELECT name, 1 - (name_embedding <=> ref.embedding) as similarity
FROM players,
     (SELECT name_embedding as embedding FROM players WHERE name = 'JÜRGEN KLOPP') ref
ORDER BY name_embedding <=> ref.embedding
LIMIT 10;
```

**Indexes:** HNSW indexes for fast similarity search.

---

## Key Indexes

- `idx_players_normalized_name` - Player name lookup
- `idx_players_name_trgm` - Fuzzy text search (trigram)
- `idx_matches_date` - Date range queries
- `idx_matches_teams` - Team-based queries
- `idx_match_lineups_player` - Player appearance lookups
- `idx_*_embedding_hnsw` - Vector similarity search

---

## Connection

```
postgresql://neondb_owner:***@ep-muddy-scene-a9tpn6pu-pooler.gwc.azure.neon.tech/neondb?sslmode=require
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `database/001_create_schema.sql` | Full schema creation |
| `database/002_materialized_views.sql` | Materialized views |
| `database/sync_sqlite_to_postgres.py` | SQLite to PostgreSQL sync |
| `database/generate_embeddings.py` | Cohere embedding generation |

---

## Entity Relationship Diagram

```
teams ─────────────┬──────────────── matches
                   │                    │
                   │         ┌──────────┼──────────┐
                   │         │          │          │
                   │    match_lineups  goals    cards
                   │         │          │          │
                   │         └──────────┴──────────┘
                   │                    │
players ───────────┴────────────────────┘
     │
     └── player_careers

coaches ── coach_careers
        │
        └── match_coaches

seasons ── season_competitions ── matches
              │
              └── competitions

chat_sessions ── chat_messages
```
