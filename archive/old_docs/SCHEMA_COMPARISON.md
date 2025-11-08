# Database Schema Comparison: 7-Table vs 19-Table Schema

## Overview

**7-Table Schema (Simple):** Current local SQLite  
**19-Table Schema (Comprehensive):** Currently in Neon Postgres

---

## Table Mapping

### 7-Table Schema → 19-Table Schema Equivalents

| 7-Table Schema | 19-Table Schema | Notes |
|----------------|-----------------|-------|
| `Seasons` | `seasons` + `season_competitions` | Simple: flat structure. Complex: normalized with competition links |
| `Opponents` | `teams` | Simple: just opponents. Complex: includes FSV Mainz as a team |
| `Players` | `players` + `player_aliases` + `player_careers` + `season_squads` | Simple: basic info. Complex: full career history + aliases |
| `Matches` | `matches` + `match_coaches` + `match_referees` | Simple: basic match data. Complex: includes officials |
| `Match_Lineups` | `match_lineups` | Similar functionality |
| `Goals` | `goals` | Similar functionality |
| `Substitutions` | `match_substitutions` | Similar functionality |
| ❌ **Missing** | `cards` | Yellow/red card tracking |
| ❌ **Missing** | `coaches` | Coach entity table |
| ❌ **Missing** | `referees` | Referee entity table |
| ❌ **Missing** | `competitions` | Competition type normalization |
| ❌ **Missing** | `match_notes` | Additional match information |
| ❌ **Missing** | `season_matchdays` | Season progression tracking |

---

## Detailed Schema Comparison

### 1. SEASONS

#### 7-Table Schema: `Seasons`
```sql
CREATE TABLE Seasons (
    season_id INTEGER PRIMARY KEY, 
    season_name TEXT UNIQUE,           -- e.g., "2023-24"
    league_name TEXT,                  -- e.g., "Bundesliga"
    total_matches INTEGER
);
```

**Pros:**
- ✅ Simple, flat structure
- ✅ League name directly in table
- ✅ Easy to query

**Cons:**
- ❌ Can't handle multiple competitions per season (Bundesliga + DFB-Pokal)
- ❌ No competition normalization (duplicate strings)
- ❌ No stage/phase tracking
- ❌ No source file tracking

#### 19-Table Schema: `seasons` + `season_competitions` + `competitions`
```sql
CREATE TABLE seasons (
    season_id INTEGER PRIMARY KEY,
    label TEXT UNIQUE,                 -- "2023-24"
    start_year INTEGER,
    end_year INTEGER,
    team_id INTEGER REFERENCES teams
);

CREATE TABLE competitions (
    competition_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,                  -- "Bundesliga"
    normalized_name TEXT UNIQUE,
    level TEXT,                        -- "first_division"
    gender TEXT                        -- "men"
);

CREATE TABLE season_competitions (
    season_competition_id INTEGER PRIMARY KEY,
    season_id INTEGER REFERENCES seasons,
    competition_id INTEGER REFERENCES competitions,
    stage_label TEXT,                  -- "Group Stage", "Knockout"
    source_path TEXT,
    UNIQUE (season_id, competition_id)
);
```

**Pros:**
- ✅ Normalized competition data (no duplicates)
- ✅ Supports multiple competitions per season
- ✅ Can track competition stages/phases
- ✅ Source file tracking for data lineage
- ✅ Structured year fields
- ✅ Can query all Bundesliga seasons easily

**Cons:**
- ❌ More complex joins required
- ❌ Overhead for simple queries

**Information Lost in 7-Table:** 
- ⚠️ **Cannot properly represent seasons with multiple competitions** (e.g., 2004-05 Bundesliga + UEFA Cup)
- ❌ No competition metadata (level, gender)
- ❌ No stage/phase tracking

---

### 2. TEAMS/OPPONENTS

#### 7-Table Schema: `Opponents`
```sql
CREATE TABLE Opponents (
    opponent_id INTEGER PRIMARY KEY, 
    opponent_name TEXT UNIQUE,
    opponent_link TEXT
);
```

**Pros:**
- ✅ Simple
- ✅ Stores opponent reference links

**Cons:**
- ❌ FSV Mainz 05 is NOT in this table (implied as "us")
- ❌ No team metadata
- ❌ No normalized name for fuzzy matching
- ❌ No team type (club, national team, youth team)

#### 19-Table Schema: `teams`
```sql
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    normalized_name TEXT UNIQUE,       -- For fuzzy matching
    team_type TEXT,                    -- "club", "national_team", "youth"
    profile_url TEXT
);
```

**Pros:**
- ✅ FSV Mainz 05 is included as a team entity
- ✅ Normalized names for better matching
- ✅ Team type classification
- ✅ Can represent all teams uniformly

**Cons:**
- ❌ Slightly more complex (but more consistent)

**Information Lost in 7-Table:**
- ❌ **FSV Mainz 05 not represented as an entity**
- ❌ No normalized names (harder to match variations)
- ❌ No team classification

---

### 3. PLAYERS

#### 7-Table Schema: `Players`
```sql
CREATE TABLE Players (
    player_id INTEGER PRIMARY KEY, 
    player_name TEXT UNIQUE,
    player_link TEXT
);
```

**Pros:**
- ✅ Extremely simple
- ✅ Sufficient for basic queries

**Cons:**
- ❌ No biographical data
- ❌ No normalized name
- ❌ No career history
- ❌ No squad assignments

#### 19-Table Schema: `players` + `player_aliases` + `player_careers` + `season_squads`
```sql
CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    normalized_name TEXT UNIQUE,
    birth_date DATE,                   -- ✅
    birth_place TEXT,                  -- ✅
    height_cm INTEGER,                 -- ✅
    weight_kg INTEGER,                 -- ✅
    primary_position TEXT,             -- ✅
    nationality TEXT,                  -- ✅
    profile_url TEXT,
    image_url TEXT
);

CREATE TABLE player_aliases (
    alias_id INTEGER PRIMARY KEY,
    player_id INTEGER REFERENCES players,
    alias TEXT,
    normalized_alias TEXT,
    UNIQUE (player_id, normalized_alias)
);

CREATE TABLE player_careers (
    career_id INTEGER PRIMARY KEY,
    player_id INTEGER REFERENCES players,
    team_name TEXT,
    start_year INTEGER,
    end_year INTEGER,
    notes TEXT
);

CREATE TABLE season_squads (
    season_squad_id INTEGER PRIMARY KEY,
    season_competition_id INTEGER REFERENCES season_competitions,
    player_id INTEGER REFERENCES players,
    position_group TEXT,
    shirt_number INTEGER,
    status TEXT,
    notes TEXT
);
```

**Pros:**
- ✅ Complete biographical information
- ✅ Career history across teams
- ✅ Alternative name handling (crucial for historical data)
- ✅ Squad assignments per season
- ✅ Normalized names for matching

**Cons:**
- ❌ More complex data model

**Information Lost in 7-Table:**
- ❌ **ALL biographical data** (birth date, place, height, weight, nationality)
- ❌ **Player career history** (where they played before/after)
- ❌ **Name variations/aliases** (important for historical players)
- ❌ **Squad numbers per season**
- ❌ **Position information**

---

### 4. MATCHES

#### 7-Table Schema: `Matches`
```sql
CREATE TABLE Matches (
    match_id INTEGER PRIMARY KEY,
    season_id INTEGER, 
    gameday INTEGER,                   -- ✅
    is_home_game BOOLEAN,              -- ✅
    opponent_id INTEGER,
    mainz_goals INTEGER,               -- ✅
    opponent_goals INTEGER,            -- ✅
    match_details_url TEXT,
    result_string TEXT
);
```

**Pros:**
- ✅ Core match data
- ✅ Simple home/away distinction
- ✅ Final scores

**Cons:**
- ❌ No match date
- ❌ No halftime scores
- ❌ No extra time/penalty tracking
- ❌ No attendance
- ❌ No venue
- ❌ No referee information
- ❌ No coach assignments

#### 19-Table Schema: `matches` + `match_coaches` + `match_referees`
```sql
CREATE TABLE matches (
    match_id INTEGER PRIMARY KEY,
    season_competition_id INTEGER,
    round_name TEXT,                   -- ✅ "Quarterfinal"
    matchday INTEGER,
    leg INTEGER,                       -- ✅ First/second leg
    match_date DATE,                   -- ✅ ✅ ✅
    kickoff_time TEXT,                 -- ✅
    venue TEXT,                        -- ✅
    attendance INTEGER,                -- ✅
    referee_id INTEGER REFERENCES referees,  -- ✅
    home_team_id INTEGER REFERENCES teams,
    away_team_id INTEGER REFERENCES teams,
    home_score INTEGER,
    away_score INTEGER,
    halftime_home INTEGER,             -- ✅
    halftime_away INTEGER,             -- ✅
    extra_time_home INTEGER,           -- ✅
    extra_time_away INTEGER,           -- ✅
    penalties_home INTEGER,            -- ✅ Penalty shootout
    penalties_away INTEGER,            -- ✅
    source_file TEXT
);

CREATE TABLE match_coaches (
    match_coach_id INTEGER PRIMARY KEY,
    match_id INTEGER REFERENCES matches,
    team_id INTEGER REFERENCES teams,
    coach_id INTEGER REFERENCES coaches,
    role TEXT                          -- ✅ "head_coach", "assistant"
);

CREATE TABLE match_referees (
    match_referee_id INTEGER PRIMARY KEY,
    match_id INTEGER REFERENCES matches,
    referee_id INTEGER REFERENCES referees,
    role TEXT                          -- ✅ "main", "assistant", "4th_official"
);
```

**Pros:**
- ✅ Complete match metadata
- ✅ Temporal data (date, time)
- ✅ Attendance tracking
- ✅ Venue information
- ✅ Halftime scores
- ✅ Extra time and penalty shootout scores
- ✅ Round/stage tracking
- ✅ Referee assignments
- ✅ Coach tracking per match

**Cons:**
- ❌ More complex joins

**Information Lost in 7-Table:**
- ❌ **Match dates** (cannot do time-series analysis)
- ❌ **Halftime scores** (cannot analyze first-half performance)
- ❌ **Extra time/penalties** (important for cup matches)
- ❌ **Attendance figures** (cannot analyze fan support trends)
- ❌ **Venue information** (some matches at different stadiums)
- ❌ **Referee information** (cannot analyze referee influence)
- ❌ **Coach tracking** (cannot see which coach managed which match)
- ❌ **Round/stage information** (quarterfinal, semifinal, etc.)
- ❌ **Leg information** (first leg vs second leg in two-legged ties)

---

### 5. MATCH LINEUPS

#### Both schemas similar functionality
7-Table has basic lineup tracking.  
19-Table adds more metadata fields.

**Information Lost in 7-Table:**
- ❌ Formation positions
- ❌ Player ratings
- ❌ Minutes played calculation
- ❌ Second yellow card tracking

---

### 6. GOALS

#### Both schemas similar
Both track goals, scorers, assists, penalties.

**Information Lost in 7-Table:**
- ❌ Stoppage time
- ❌ Goal type details (free kick, header, body part)
- ❌ Assist type

---

### 7. CARDS (Yellow/Red)

#### 7-Table Schema: **MISSING ENTIRELY** ❌
Card information is embedded in `Match_Lineups` table:
- `yellow_card BOOLEAN`
- `red_card BOOLEAN`

**Limitations:**
- ❌ No timing information (which minute?)
- ❌ No stoppage time
- ❌ Cannot track second yellow = red
- ❌ Cannot track cards for substitutes who didn't start
- ❌ Limited to one yellow per player per match

#### 19-Table Schema: `cards`
```sql
CREATE TABLE cards (
    card_id INTEGER PRIMARY KEY,
    match_id INTEGER REFERENCES matches,
    team_id INTEGER REFERENCES teams,
    player_id INTEGER REFERENCES players,
    minute INTEGER,                    -- ✅ When?
    stoppage INTEGER,                  -- ✅ Stoppage time
    card_type TEXT                     -- ✅ yellow/red/second_yellow
);
```

**Pros:**
- ✅ Precise timing
- ✅ Can track multiple cards per player
- ✅ Distinguishes second yellow from straight red
- ✅ Stoppage time tracking
- ✅ Independent entity (doesn't require lineup entry)

**Information Lost in 7-Table:**
- ❌ **Card timing** (crucial for analysis)
- ❌ **Multiple cards per player**
- ❌ **Second yellow distinction**
- ❌ **Cards for non-lineup players** (coaching staff, bench)

---

### 8. MATCH_NOTES & SEASON_MATCHDAYS

#### 7-Table Schema: **MISSING** ❌

#### 19-Table Schema: Additional tables
```sql
CREATE TABLE match_notes (
    note_id INTEGER PRIMARY KEY,
    match_id INTEGER REFERENCES matches,
    note TEXT,
    note_type TEXT                     -- "incident", "weather", "commentary"
);

CREATE TABLE season_matchdays (
    season_matchday_id INTEGER PRIMARY KEY,
    season_competition_id INTEGER,
    matchday INTEGER,
    date DATE,
    position INTEGER,                  -- ✅ League position
    points INTEGER,                    -- ✅ Points accumulated
    goals_for INTEGER,
    goals_against INTEGER,
    goal_difference INTEGER
);
```

**Information Lost in 7-Table:**
- ❌ **Season progression tracking** (how position changed over time)
- ❌ **Match notes/incidents**
- ❌ **Historical league table snapshots**

---

## Summary: Information Lost in 7-Table Schema

### 🔴 CRITICAL Data Loss

1. **Match Dates** - Cannot do any time-based analysis
2. **Biographical Player Data** - No birth dates, nationality, positions
3. **Card Timing** - When cards were issued
4. **Multiple Competitions per Season** - UEFA Cup + Bundesliga
5. **Coach & Referee Tracking** - Who managed/officiated matches

### 🟡 SIGNIFICANT Data Loss

6. **Halftime/Extra Time Scores** - Important for match flow analysis
7. **Attendance & Venue** - Fan support trends
8. **Player Career History** - Where players came from/went to
9. **Season Progression** - League table snapshots
10. **Round/Stage Information** - Quarterfinal, semifinal, etc.
11. **Match Notes** - Additional context

### 🟢 MINOR Data Loss

12. **Player Aliases** - Alternative name spellings
13. **Formation Positions** - Tactical positions
14. **Normalized Names** - Makes fuzzy matching harder
15. **Team Classification** - Club vs national team

---

## Recommendations

### Use 19-Table Schema If You Need:
- ✅ Complete football analytics
- ✅ Time-series analysis (trends over time)
- ✅ Player biographical research
- ✅ Coach/referee analysis
- ✅ Multi-competition tracking
- ✅ Card discipline analysis
- ✅ Historical league standings

### Use 7-Table Schema If You Need:
- ✅ Simple match result queries
- ✅ Basic player statistics (goals, appearances)
- ✅ Minimal storage/complexity
- ✅ Quick prototyping
- ✅ Single competition focus

---

## Data Volume Comparison

### 7-Table Schema (Current Local SQLite)
```
Seasons:        109 rows
Opponents:    2,518 rows
Players:      7,995 rows
Matches:      2,774 rows
Match_Lineups: 40,437 rows
Goals:         6,079 rows
Substitutions: 8,689 rows
────────────────────────────
TOTAL:        68,601 rows
```

### 19-Table Schema (Neon Postgres)
```
teams:              290 rows
competitions:         3 rows
seasons:            121 rows
season_competitions: 175 rows
referees:           864 rows
coaches:            563 rows
players:         10,688 rows  ⬆️ +33% more players
player_aliases:       0 rows  (empty, ready for use)
player_careers:   4,627 rows  ✨ NEW
season_squads:      927 rows  ✨ NEW
matches:          3,263 rows  ⬆️ +18% more matches
match_coaches:    5,015 rows  ✨ NEW
match_referees:   2,876 rows  ✨ NEW
match_lineups:   84,270 rows  ⬆️ +108% more lineup entries
match_substitutions: 10,162 rows ⬆️ +17% more subs
goals:            6,819 rows  ⬆️ +12% more goals
cards:           11,075 rows  ✨ NEW
match_notes:          0 rows  (empty, ready for use)
season_matchdays: 1,775 rows  ✨ NEW
────────────────────────────────
TOTAL:          143,513 rows  ⬆️ +109% more data
```

**The 19-table schema contains 2x more data** and significantly more metadata.

---

## Migration Recommendation

**If you want to keep your new Euro competition data**, I recommend:

### Option A: Migrate to 19-Table Schema
1. Re-parse your HTML archive with `comprehensive_fsv_parser.py` to generate the 19-table schema
2. This will include all Euro competition matches
3. Upload to Postgres with full metadata

### Option B: Add Euro Data to Existing 19-Table Schema
1. Parse only the new Euro competition matches
2. Insert them into the existing Postgres 19-table schema
3. Keep the richer metadata

### Option C: Accept 7-Table Simplicity
1. Replace Postgres with current 7-table schema
2. Lose metadata but gain simplicity
3. Accept that detailed analysis won't be possible

**Which approach would you prefer?**

