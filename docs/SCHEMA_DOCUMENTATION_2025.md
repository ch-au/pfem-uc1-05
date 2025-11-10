# FSV Mainz 05 Database - Schema Documentation
**Database:** Neon PostgreSQL Cloud + SQLite (Parser Output)
**Version:** November 2025
**Last Updated:** 2025-11-09
**Status:** ✅ Production Ready

---

## Quick Stats

| Metric | Count |
|--------|-------|
| **Tables** | 26 |
| **Materialized Views** | 4 |
| **Indexes** | 107 |
| **Total Matches** | 3,956 |
| **Total Players** | 9,955 |
| **Total Goals** | 8,312 |
| **Total Cards** | 5,768 |
| **Total Lineups** | 91,475 |
| **Profirest Matches** | 668 |

---

## Recent Changes (November 2025)

### ✅ Schema Fixes
- **Migration 004:** Added unique constraints to prevent duplicate events
- **Migration 005:** Added `team_id` foreign keys to `player_careers` and `season_squads`
- **Migration 006:** Merged duplicate Mainz team entries (team_id 1 and 31)
- **Migration 007:** Created 4 materialized views for performance

### ✅ Profirest Matches Integration (Nov 10, 2025)
- **Parser Enhancement:** Added multi-match file parsing for profirest*.html files
- **Data Import:** Successfully parsed and synced 668 profirest matches (1905-1960s era)
- **Related Data:** Synced 6,133 lineups and 1,316 goals for historical matches
- **Team Expansion:** Added 257 historical opponent teams to database
- **Coverage:** Increased total match count from 3,354 to 3,956 (+18%)

### ✅ Key Improvements
- **Team Consolidation:** All Mainz matches now under single `team_id = 1` (was split across 2 teams)
- **Data Integrity:** Unique constraints prevent duplicate cards, goals, lineups, substitutions
- **Query Performance:** Materialized views provide 100-400x speedup
- **Foreign Keys:** Easy joins between `player_careers`, `season_squads`, and `teams`
- **Historical Coverage:** Complete match data from 1905-2025 (120 years)

---

## Table Overview

### Core Tables (26 total)

| Table | Rows | Purpose | Key Changes |
|-------|------|---------|-------------|
| **teams** | 585 | Teams (Mainz + opponents) | +257 historical teams from profirest |
| **players** | 9,955 | Player master data | Full name enrichment |
| **coaches** | 566 | Coach master data | Full name enrichment (13.6%) |
| **referees** | 870 | Referee master data | - |
| **competitions** | 23 | Competitions | - |
| **seasons** | 121 | Seasons (1905-2026) | - |
| **season_competitions** | 175 | Season-competition links | - |
| **matches** | 3,956 | Match results | +668 profirest matches |
| **goals** | 8,312 | Goal events | ✅ Unique constraint added |
| **cards** | 5,768 | Card events | ✅ Unique constraint added |
| **match_lineups** | 91,475 | Player appearances | ✅ Unique constraint added |
| **match_substitutions** | 10,029 | Substitutions | ✅ Unique constraint added |
| **match_coaches** | 2,832 | Coach assignments | - |
| **match_referees** | 2,879 | Referee assignments | - |
| **player_careers** | 4,760 | Player career history | ✅ Added optional `team_id` FK |
| **season_squads** | 434 | Squad assignments | ✅ Added required `team_id` FK |
| **coach_careers** | 522 | Coach career history | - |
| **player_aliases** | 0 | Alternative player names | - |
| **match_notes** | 0 | Match notes | - |
| **season_matchdays** | 1,775 | Season standings | - |
| **chat_sessions** | 0 | Chat sessions (quiz app) | - |
| **chat_messages** | 0 | Chat messages (quiz app) | - |
| **quiz_games** | 0 | Quiz games | - |
| **quiz_questions** | 0 | Quiz questions | - |
| **quiz_rounds** | 0 | Quiz rounds | - |
| **quiz_answers** | 0 | Quiz answers | - |

### Materialized Views (4 total)

| View | Rows | Purpose | Refresh |
|------|------|---------|---------|
| **mainz_match_results** | 3,305 | All Mainz matches with details | Daily |
| **player_career_stats** | 1,172 | Aggregated player statistics | Weekly |
| **season_performance** | 196 | Season-by-season performance | Weekly |
| **competition_statistics** | 23 | All-time stats by competition | Monthly |

---

## Detailed Table Schemas

### 1. teams

**Purpose:** All teams (FSV Mainz 05 and opponents)

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| team_id | INTEGER | PRIMARY KEY | **Mainz 05 = 1 (always)** |
| name | TEXT | UNIQUE, NOT NULL | Official team name |
| normalized_name | TEXT | UNIQUE | Lowercase, accent-stripped for matching |
| team_type | TEXT | | Usually "club" |
| profile_url | TEXT | | Link to team profile page |
| name_embedding | vector(1024) | | Cohere embed-v4.0 for semantic search |

**Important:** FSV Mainz 05 **always** has `team_id = 1`. This was consolidated in Migration 006.

**Indexes:**
- `idx_teams_normalized_name`
- `idx_teams_name_embedding_hnsw` (vector search)

---

### 2. players

**Purpose:** Player master data with biographical information

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| player_id | INTEGER | PRIMARY KEY | Unique player identifier |
| name | TEXT | UNIQUE, NOT NULL | Player name |
| normalized_name | TEXT | UNIQUE | For fuzzy matching |
| birth_date | DATE | | |
| birth_place | TEXT | | |
| height_cm | INTEGER | | Height in centimeters |
| weight_kg | INTEGER | | Weight in kilograms |
| primary_position | TEXT | | e.g., "Stürmer", "Mittelfeld" |
| nationality | TEXT | | Nationality |
| profile_url | TEXT | | Link to player profile |
| image_url | TEXT | | Link to player image |
| name_embedding | vector(1024) | | Cohere embed for semantic search |

**Indexes:**
- `idx_players_normalized_name`
- `idx_players_name`
- `idx_players_name_embedding_hnsw`

---

### 3. matches

**Purpose:** Match master data with scores and metadata

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| match_id | INTEGER | PRIMARY KEY | Unique match identifier |
| season_competition_id | INTEGER | FK → season_competitions | Links to season/competition |
| round_name | TEXT | | e.g., "1. Spieltag", "Achtelfinale" |
| matchday | INTEGER | | Matchday number |
| leg | INTEGER | | Leg number for two-legged ties |
| match_date | DATE | | Match date |
| kickoff_time | TEXT | | Kickoff time |
| venue | TEXT | | Stadium name |
| attendance | INTEGER | | Crowd size |
| referee_id | INTEGER | FK → referees | Main referee |
| home_team_id | INTEGER | FK → teams | Home team |
| away_team_id | INTEGER | FK → teams | Away team |
| home_score | INTEGER | | Final home score |
| away_score | INTEGER | | Final away score |
| halftime_home | INTEGER | | Halftime home score |
| halftime_away | INTEGER | | Halftime away score |
| extra_time_home | INTEGER | | Extra time home score |
| extra_time_away | INTEGER | | Extra time away score |
| penalties_home | INTEGER | | Penalty shootout home |
| penalties_away | INTEGER | | Penalty shootout away |
| source_file | TEXT | | Source HTML file path |

**Unique Constraint:** `(season_competition_id, source_file)`

**Indexes:**
- `idx_matches_date`
- `idx_matches_season_comp`
- `idx_matches_home_team`
- `idx_matches_away_team`

---

### 4. goals

**Purpose:** Goal events

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| goal_id | INTEGER | PRIMARY KEY | |
| match_id | INTEGER | FK → matches ON DELETE CASCADE | |
| team_id | INTEGER | FK → teams | Scoring team |
| player_id | INTEGER | FK → players | Scorer (NULL for own goals) |
| assist_player_id | INTEGER | FK → players | Assist provider |
| minute | INTEGER | | Goal minute |
| stoppage | INTEGER | | Stoppage time |
| score_home | INTEGER | | Home score after goal |
| score_away | INTEGER | | Away score after goal |
| event_type | TEXT | | 'penalty', 'own_goal', or NULL |

**✅ NEW: Unique Constraint (Migration 004)**
```sql
CREATE UNIQUE INDEX idx_goals_unique_event
ON goals (match_id, COALESCE(player_id, -1), minute, COALESCE(stoppage, 0));
```
Prevents duplicate goal events.

**Indexes:**
- `idx_goals_match`
- `idx_goals_player`
- `idx_goals_assist`
- `idx_goals_unique_event` (prevents duplicates)

---

### 5. cards

**Purpose:** Yellow and red card events

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| card_id | INTEGER | PRIMARY KEY | |
| match_id | INTEGER | FK → matches ON DELETE CASCADE | |
| team_id | INTEGER | FK → teams | |
| player_id | INTEGER | FK → players | |
| minute | INTEGER | | Card minute (often NULL!) |
| stoppage | INTEGER | | Stoppage time |
| card_type | TEXT | | 'yellow', 'red', 'second_yellow' |

**Note:** 94.5% of cards have NULL minute (card minute not recorded in historical data).

**✅ NEW: Unique Constraint (Migration 004)**
```sql
CREATE UNIQUE INDEX idx_cards_unique_event
ON cards (match_id, player_id, COALESCE(minute, -1), COALESCE(stoppage, 0), card_type);
```
Prevents duplicate card events.

**Indexes:**
- `idx_cards_match`
- `idx_cards_player`
- `idx_cards_unique_event` (prevents duplicates)

---

### 6. match_lineups

**Purpose:** Player appearances (starters and substitutes)

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| lineup_id | INTEGER | PRIMARY KEY | |
| match_id | INTEGER | FK → matches ON DELETE CASCADE | |
| team_id | INTEGER | FK → teams | |
| player_id | INTEGER | FK → players | |
| shirt_number | INTEGER | | Jersey number |
| is_starter | BOOLEAN | | TRUE = starting XI, FALSE = substitute |
| minute_on | INTEGER | | Substitution on minute |
| stoppage_on | INTEGER | | Stoppage time |
| minute_off | INTEGER | | Substitution off minute |
| stoppage_off | INTEGER | | Stoppage time |

**✅ NEW: Unique Constraint (Migration 004)**
```sql
CREATE UNIQUE INDEX idx_lineups_unique_entry
ON match_lineups (match_id, player_id, team_id);
```
Prevents duplicate lineup entries (one entry per player per match per team).

**Indexes:**
- `idx_lineups_match`
- `idx_lineups_player`
- `idx_lineups_team`
- `idx_lineups_unique_entry` (prevents duplicates)

---

### 7. player_careers

**Purpose:** Player career history across all clubs

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| career_id | INTEGER | PRIMARY KEY | |
| player_id | INTEGER | FK → players ON DELETE CASCADE | |
| team_name | TEXT | NOT NULL | Club name (for external clubs) |
| **team_id** | **INTEGER** | **FK → teams** | **✅ NEW! (Migration 005)** |
| start_year | INTEGER | | Career start year |
| end_year | INTEGER | | Career end year |
| notes | TEXT | | Additional notes |

**✅ NEW in Migration 005:**
- Added optional `team_id` column
- 53% of careers (2,539 out of 4,760) now linked to teams table
- 47% remain as text-only for external clubs not in database

**Why both `team_name` and `team_id`?**
- `team_name`: Flexible text for clubs not in database
- `team_id`: Foreign key for clubs in database (enables JOINs)

**Indexes:**
- `idx_player_careers_team`
- `idx_player_careers_player_team`

---

### 8. season_squads

**Purpose:** Squad assignments per season/competition

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| season_squad_id | INTEGER | PRIMARY KEY | |
| season_competition_id | INTEGER | FK → season_competitions | |
| player_id | INTEGER | FK → players | |
| **team_id** | **INTEGER** | **FK → teams NOT NULL** | **✅ NEW! (Migration 005)** |
| position_group | TEXT | | Position category |
| shirt_number | INTEGER | | Squad number |
| status | TEXT | | Player status |
| notes | TEXT | | Additional notes |

**✅ NEW in Migration 005:**
- Added required `team_id` column
- All 434 entries set to `team_id = 1` (FSV Mainz 05)
- Enables filtering squads by team

**Unique Constraint:** `(season_competition_id, player_id, position_group)`

**Indexes:**
- `idx_season_squads_team`
- `idx_season_squads_season_team`
- `idx_season_squads_player_team`

---

## Materialized Views

### 1. mainz_match_results

**Purpose:** Comprehensive match data for all Mainz 05 matches

**Columns:**
- `match_id`, `match_date`, `season`, `start_year`, `end_year`
- `competition`, `competition_level`, `round_name`, `matchday`
- `home_team`, `away_team`, `home_score`, `away_score`
- `halftime_home`, `halftime_away`
- `mainz_location` ('Home' or 'Away')
- `mainz_score`, `opponent_score`
- `result` ('W', 'D', or 'L' from Mainz perspective)
- `venue`, `attendance`, `referee`
- `mainz_scorers` (JSON array of goal events)
- `mainz_cards` (JSON array of card events)

**Row Count:** 3,956 matches

**Refresh Frequency:** Daily or after match imports

**Example Query:**
```sql
SELECT match_date, home_team, home_score, away_score, away_team, result
FROM mainz_match_results
WHERE season = '2023-24' AND competition = 'Bundesliga'
ORDER BY match_date DESC;
```

**Indexes:**
- `idx_mainz_match_results_match_id` (UNIQUE)
- `idx_mainz_match_results_date`
- `idx_mainz_match_results_season`
- `idx_mainz_match_results_competition`
- `idx_mainz_match_results_result`

---

### 2. player_career_stats

**Purpose:** Aggregated career statistics for all Mainz 05 players

**Columns:**
- `player_id`, `name`, `nationality`, `primary_position`
- `birth_date`, `height_cm`, `weight_kg`
- `total_appearances`, `total_starts`, `total_sub_appearances`
- `total_goals`, `penalty_goals`, `open_play_goals`
- `total_assists`
- `yellow_cards`, `second_yellow_cards`, `red_cards`
- `first_match`, `last_match`
- `goals_per_match`

**Row Count:** 1,172 players (only those with appearances)

**Refresh Frequency:** Weekly or after match imports

**Example Query:**
```sql
SELECT name, total_goals, total_appearances, goals_per_match
FROM player_career_stats
ORDER BY total_goals DESC
LIMIT 20;
```

**Top 5 Scorers:**
| name | total_goals | total_appearances |
|------|-------------|-------------------|
| Bopp | 142 | 344 |
| Mähn | 87 | 323 |
| Klier | 82 | 193 |
| C. Tripp | 51 | 118 |
| Thurk | 49 | 212 |

**Indexes:**
- `idx_player_career_stats_player_id` (UNIQUE)
- `idx_player_career_stats_goals`
- `idx_player_career_stats_appearances`
- `idx_player_career_stats_name`

---

### 3. season_performance

**Purpose:** Season-by-season performance in each competition

**Columns:**
- `season`, `start_year`, `end_year`, `competition`
- `matches_played`, `wins`, `draws`, `losses`
- `goals_for`, `goals_against`, `goal_difference`
- `win_percentage`

**Row Count:** 196 season/competition combinations

**Refresh Frequency:** Weekly or after season completion

**Example Query:**
```sql
SELECT season, wins, draws, losses, goals_for, goals_against, win_percentage
FROM season_performance
WHERE competition = 'Bundesliga'
ORDER BY start_year DESC
LIMIT 10;
```

**Indexes:**
- `idx_season_performance_season`
- `idx_season_performance_competition`
- `idx_season_performance_year`

---

### 4. competition_statistics

**Purpose:** All-time statistics by competition

**Columns:**
- `competition`, `competition_level`
- `seasons_participated`, `first_season`, `last_season`
- `total_matches`, `wins`, `draws`, `losses`
- `goals_for`, `goals_against`
- `win_percentage`

**Row Count:** 23 competitions

**Refresh Frequency:** Monthly or after significant data imports

**Example Query:**
```sql
SELECT competition, total_matches, wins, win_percentage
FROM competition_statistics
ORDER BY total_matches DESC;
```

**Top 5 Competitions:**
| competition | total_matches | wins | win_percentage |
|-------------|---------------|------|----------------|
| Bundesliga | 652 | 216 | 33.1% |
| 2. Bundesliga | 568 | 217 | 38.2% |
| Oberliga Südwest | 408 | 146 | 35.8% |
| Amateur-Oberliga Südwest | 384 | 213 | 55.5% |
| Regionalliga Südwest | 342 | 167 | 48.8% |

**Indexes:**
- `idx_competition_statistics_competition` (UNIQUE)
- `idx_competition_statistics_matches`

---

## Query Examples

### Example 1: Recent Bundesliga Matches
```sql
SELECT match_date, home_team, home_score, away_score, away_team, result
FROM mainz_match_results
WHERE competition = 'Bundesliga'
  AND match_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY match_date DESC;
```

### Example 2: Top Goal Scorers with Details
```sql
SELECT
    name,
    total_goals,
    penalty_goals,
    open_play_goals,
    total_assists,
    total_appearances,
    ROUND(goals_per_match, 2) as gpg
FROM player_career_stats
WHERE total_goals > 10
ORDER BY goals_per_match DESC
LIMIT 20;
```

### Example 3: Season Comparison
```sql
SELECT
    season,
    competition,
    matches_played,
    wins || '-' || draws || '-' || losses as record,
    win_percentage || '%' as win_rate,
    goals_for || ':' || goals_against as goal_record
FROM season_performance
WHERE competition = 'Bundesliga'
ORDER BY start_year DESC;
```

### Example 4: Head-to-Head Record
```sql
SELECT
    away_team as opponent,
    COUNT(*) as matches,
    SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result = 'D' THEN 1 ELSE 0 END) as draws,
    SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) as losses
FROM mainz_match_results
WHERE mainz_location = 'Home'
  AND competition = 'Bundesliga'
GROUP BY away_team
HAVING COUNT(*) >= 10
ORDER BY wins DESC;
```

---

## Maintenance

### Daily Tasks
```sql
-- Refresh match-related views after match imports
REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;
REFRESH MATERIALIZED VIEW CONCURRENTLY player_career_stats;
```

### Weekly Tasks
```sql
-- Refresh season performance
REFRESH MATERIALIZED VIEW CONCURRENTLY season_performance;
```

### Monthly Tasks
```sql
-- Refresh competition statistics
REFRESH MATERIALIZED VIEW CONCURRENTLY competition_statistics;

-- Update table statistics
ANALYZE matches;
ANALYZE players;
ANALYZE goals;
ANALYZE cards;
```

---

## Migration History

| Migration | Date | Purpose |
|-----------|------|---------|
| 004 | 2025-11-09 | Add unique constraints to prevent duplicates |
| 005 | 2025-11-09 | Add team_id foreign keys to player_careers and season_squads |
| 006 | 2025-11-09 | Merge duplicate Mainz team entries (id 1 and 31) |
| 007 | 2025-11-09 | Create materialized views for performance |

**See:** `database/migrations/` for SQL files

---

## Performance

### Before Optimizations
- Match queries: ~800ms (5 JOINs)
- Player stats: ~1,200ms (aggregation across 85K rows)
- Season performance: ~600ms (multiple aggregations)

### After Optimizations (Materialized Views)
- Match queries: **~5ms** (100-400x faster!)
- Player stats: **~3ms**
- Season performance: **~2ms**

---

## Data Quality

### Coverage
- **Seasons:** 121 (1905-2026)
- **Matches:** 3,956 (all properly attributed to team_id = 1)
  - Including 668 profirest matches from early history (1905-1960s)
- **Players:** 9,955 (cleaned, full name enrichment where available)
- **Embeddings:** 100% coverage (all players and teams have vector embeddings)

### Constraints
- ✅ Unique constraints prevent duplicate events
- ✅ Foreign keys ensure referential integrity
- ✅ Check constraints validate data values
- ✅ NOT NULL constraints enforce required fields

---

## Notes

1. **Team ID = 1:** FSV Mainz 05 always has `team_id = 1`. This is enforced by the parser.

2. **Historical Data:** Older matches may have incomplete data (e.g., missing card minutes, attendance).

3. **Vector Search:** Uses Cohere embed-v4.0 (1024 dimensions) for semantic player/team name matching.

4. **Quiz Tables:** Currently empty, schema exists for future use.

---

**End of Documentation**

**For Quick Reference:** See [QUICK_START.md](../QUICK_START.md)
**For Complete Details:** See [FINAL_SCHEMA_AND_OPTIMIZATIONS.md](../FINAL_SCHEMA_AND_OPTIMIZATIONS.md)
