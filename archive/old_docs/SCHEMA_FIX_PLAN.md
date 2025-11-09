# Schema Fix Plan - Foundation First
**Date:** 2025-11-09
**Priority:** CRITICAL - Fix before any optimizations

---

## Problem Statement

Before we can optimize, we need to fix the foundation:

1. **Missing unique constraints** - No protection against duplicate cards/goals/lineups
2. **Team name variations** - Mainz 05 historical names not all normalized correctly
3. **Poor join support** - `player_careers` and `season_squads` lack `team_id` FK
4. **Schema mismatch** - PostgreSQL schema differs from SQLite parser output

---

## Critical Fixes Required

### 1. Add Unique Constraints (Prevent Duplicates)

**Problem:** Parser has duplicate checking logic, but database has no constraints to enforce it.

**Current State:**
- cards table: NO unique constraint
- goals table: NO unique constraint
- match_lineups table: NO unique constraint
- match_substitutions table: NO unique constraint

**Solution:** Add unique constraints matching parser's duplicate logic

```sql
-- Cards: Prevent duplicate card events
-- Parser logic: Lines 1028-1043 check (match_id, player_id, minute, card_type)
CREATE UNIQUE INDEX idx_cards_unique_event
ON public.cards (match_id, player_id, COALESCE(minute, -1), COALESCE(stoppage, 0), card_type);

-- Goals: Prevent duplicate goals
-- Parser logic: Lines 976-984 check (match_id, player_id, minute, stoppage)
CREATE UNIQUE INDEX idx_goals_unique_event
ON public.goals (match_id, COALESCE(player_id, -1), minute, COALESCE(stoppage, 0));

-- Match Lineups: Prevent duplicate lineup entries
-- Parser logic: Lines 888-894 check (match_id, player_id, team_id)
CREATE UNIQUE INDEX idx_lineups_unique_entry
ON public.match_lineups (match_id, player_id, team_id);

-- Match Substitutions: Prevent duplicate substitutions
-- Parser logic: Lines 936-942 check (match_id, player_on_id, player_off_id, minute, stoppage)
CREATE UNIQUE INDEX idx_substitutions_unique_event
ON public.match_substitutions (match_id, player_on_id, player_off_id, minute, COALESCE(stoppage, -1));
```

---

### 2. Fix Team Name Normalization

**Problem:** Historical Mainz 05 names should all map to `team_id = 1`

**Mainz 05 Historical Names (All Same Club):**
- 1905: "1. Mainzer Fußballclub Hassia 1905"
- 1912: "1. Mainzer Fussballverein Hassia 05" → "1. Mainzer Fussballverein 05"
- 1919: "1. Mainzer Fußball- und Sportverein 05" (after fusion with SV 1908 Mainz)
- Today: "1. Fußball- und Sport-Verein Mainz 05 e.V." → "1. FSV Mainz 05"

**Other Mainz Teams (DIFFERENT clubs):**
- FC Basara Mainz (different club)
- SVW Mainz (different club - SpVgg Weisenau Mainz)
- Stadtauswahl Mainz (city selection team)

**Parser Already Has This Logic (Lines 488-510):**
```python
mainz_patterns = [
    'mainzer fc hassia',
    'mainzer fsv',
    'mainzer fv',
    'viktoria 05 mainz',
    'reichsbahn',  # Reichsbahn TSV Mainz 05
    'luftwaffe-sv mainz',
    'mainzer tv',
    'spvgg weisenau mainz',
]
```

**Missing Patterns to Add:**
```python
'mainzer fußballclub hassia',
'mainzer fussballverein hassia',
'mainzer fußball- und sportverein',
'1. mainzer fc',
'1. mainzer fv',
'1. mainzer fsv',
```

**Recommendation:** Update parser's `get_or_create_team()` method to include all historical Mainz 05 variations.

---

### 3. Improve Foreign Key Relationships

**Problem:** Cannot easily join across tables due to missing FKs.

#### Issue 3a: `player_careers` Uses TEXT Instead of FK

**Current Schema:**
```sql
CREATE TABLE player_careers (
    career_id INTEGER PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    team_name TEXT NOT NULL,  -- ⚠️ Should be team_id FK!
    start_year INTEGER,
    end_year INTEGER,
    notes TEXT
);
```

**Impact:**
- Cannot join with `teams` table
- Data denormalization (team name stored multiple times)
- Inconsistent team names across records

**Options:**

**Option A: Add Optional team_id Column (RECOMMENDED)**
```sql
-- Add optional team_id column for known teams
ALTER TABLE player_careers
ADD COLUMN team_id INTEGER REFERENCES teams(team_id);

-- Backfill team_id where team_name matches
UPDATE player_careers pc
SET team_id = t.team_id
FROM teams t
WHERE LOWER(pc.team_name) = LOWER(t.name)
   OR pc.team_name = t.normalized_name;

-- Index for fast lookups
CREATE INDEX idx_player_careers_team ON player_careers(team_id);
CREATE INDEX idx_player_careers_player_team ON player_careers(player_id, team_id);
```

**Benefits:**
- Maintains flexibility for unknown teams (keep team_name for external clubs)
- Enables fast joins for known teams
- No data loss
- Backward compatible

**Option B: Full Migration to team_id (BREAKING CHANGE)**
```sql
-- Create lookup table for external teams first
-- Then migrate all team_name → team_id
-- Drop team_name column
```

**Decision: Use Option A** - Add optional `team_id` without removing `team_name`.

#### Issue 3b: `season_squads` Missing team_id

**Current Schema:**
```sql
CREATE TABLE season_squads (
    season_squad_id INTEGER PRIMARY KEY,
    season_competition_id INTEGER REFERENCES season_competitions,
    player_id INTEGER REFERENCES players(player_id),
    position_group TEXT,
    shirt_number INTEGER,
    status TEXT,
    notes TEXT
    -- Missing: team_id INTEGER REFERENCES teams(team_id)
);
```

**Impact:**
- Assumes all squads are FSV Mainz 05 only
- Cannot track opponent squads
- Limits historical research potential

**Solution:**
```sql
-- Add team_id column with default to FSV Mainz 05
ALTER TABLE season_squads
ADD COLUMN team_id INTEGER REFERENCES teams(team_id) DEFAULT 1;

-- Update existing records to explicitly set team_id
UPDATE season_squads SET team_id = 1;

-- Remove default for future inserts (make it explicit)
ALTER TABLE season_squads ALTER COLUMN team_id DROP DEFAULT;

-- Make it NOT NULL
ALTER TABLE season_squads ALTER COLUMN team_id SET NOT NULL;

-- Add index
CREATE INDEX idx_season_squads_team ON season_squads(team_id);
CREATE INDEX idx_season_squads_season_team ON season_squads(season_competition_id, team_id);
```

---

### 4. Quiz Tables (For Future)

**Current State:** All quiz tables are empty (0 games, 0 questions, 0 answers).

**Recommendation:**
- Skip quiz-related optimizations until data exists
- Schema is correct (uses `topic` TEXT instead of `category_id` FK)
- No changes needed

---

## Implementation Plan

### Phase 1: Add Protective Constraints (Immediate)

```sql
-- File: database/migrations/004_add_unique_constraints.sql

-- ============================================================================
-- MIGRATION 004: Add Unique Constraints for Data Integrity
-- ============================================================================
-- Purpose: Prevent duplicate events in cards, goals, lineups, substitutions
-- Date: 2025-11-09
--
-- This enforces the duplicate prevention logic already in the parser.
-- ============================================================================

-- 1. Cards unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_unique_event
ON public.cards (match_id, player_id, COALESCE(minute, -1), COALESCE(stoppage, 0), card_type);

-- 2. Goals unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_goals_unique_event
ON public.goals (match_id, COALESCE(player_id, -1), minute, COALESCE(stoppage, 0));

-- 3. Match lineups unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_lineups_unique_entry
ON public.match_lineups (match_id, player_id, team_id);

-- 4. Substitutions unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_substitutions_unique_event
ON public.match_substitutions (match_id, player_on_id, player_off_id, minute, COALESCE(stoppage, -1));

-- Analyze tables for query planner
ANALYZE public.cards;
ANALYZE public.goals;
ANALYZE public.match_lineups;
ANALYZE public.match_substitutions;
```

### Phase 2: Improve Foreign Keys (After Testing)

```sql
-- File: database/migrations/005_add_team_foreign_keys.sql

-- ============================================================================
-- MIGRATION 005: Add team_id Foreign Keys
-- ============================================================================
-- Purpose: Enable easy joins across player_careers and season_squads
-- Date: 2025-11-09
-- ============================================================================

-- 1. Add optional team_id to player_careers
ALTER TABLE player_careers
ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(team_id);

-- Backfill known teams
UPDATE player_careers pc
SET team_id = t.team_id
FROM teams t
WHERE pc.team_id IS NULL
  AND (LOWER(pc.team_name) = LOWER(t.name) OR pc.team_name = t.normalized_name);

CREATE INDEX IF NOT EXISTS idx_player_careers_team ON player_careers(team_id);
CREATE INDEX IF NOT EXISTS idx_player_careers_player_team ON player_careers(player_id, team_id);

-- 2. Add team_id to season_squads (default to FSV Mainz 05)
ALTER TABLE season_squads
ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(team_id) DEFAULT 1;

UPDATE season_squads SET team_id = 1 WHERE team_id IS NULL;

ALTER TABLE season_squads ALTER COLUMN team_id DROP DEFAULT;
ALTER TABLE season_squads ALTER COLUMN team_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_season_squads_team ON season_squads(team_id);
CREATE INDEX IF NOT EXISTS idx_season_squads_season_team ON season_squads(season_competition_id, team_id);

-- Analyze for query planner
ANALYZE public.player_careers;
ANALYZE public.season_squads;
```

### Phase 3: Update Parser (For Next Re-Parse)

**File:** `parsing/comprehensive_fsv_parser.py`

**Changes needed:**

1. **Add missing Mainz historical names** (lines 492-502):
```python
mainz_patterns = [
    # Existing patterns
    'mainzer fc hassia',
    'mainzer fsv',
    'mainzer fv',
    'viktoria 05 mainz',
    'reichsbahn',
    'luftwaffe-sv mainz',
    'mainzer tv',
    'spvgg weisenau mainz',
    # ADD THESE:
    'mainzer fußballclub hassia',
    'mainzer fussballverein hassia',
    'mainzer fußball- und sportverein',
    'mainzer fußball und sportverein',
    '1. mainzer fc',
]
```

2. **Add team_id to season_squads inserts** (find where season_squads are inserted)

3. **Add team_id to player_careers inserts** (find where player_careers are inserted)

---

## Testing Plan

### Test 1: Verify Unique Constraints Work

```sql
-- Should succeed (new unique card)
INSERT INTO cards (match_id, team_id, player_id, minute, stoppage, card_type)
VALUES (1, 1, 1, 45, 0, 'yellow');

-- Should FAIL with unique constraint violation
INSERT INTO cards (match_id, team_id, player_id, minute, stoppage, card_type)
VALUES (1, 1, 1, 45, 0, 'yellow');
```

### Test 2: Verify Team Name Normalization

```sql
-- All these should return team_id = 1:
SELECT get_or_create_team('1. Mainzer FC Hassia 1905');
SELECT get_or_create_team('1. Mainzer Fussballverein Hassia 05');
SELECT get_or_create_team('1. FSV Mainz 05');
```

### Test 3: Verify Foreign Key Joins Work

```sql
-- Should work: Join player_careers with teams
SELECT
    p.name as player_name,
    t.name as team_name,
    pc.start_year,
    pc.end_year
FROM player_careers pc
JOIN players p ON pc.player_id = p.player_id
LEFT JOIN teams t ON pc.team_id = t.team_id
WHERE t.team_id = 1
LIMIT 10;

-- Should work: Join season_squads with teams
SELECT
    s.label as season,
    c.name as competition,
    t.name as team,
    p.name as player,
    ss.position_group
FROM season_squads ss
JOIN players p ON ss.player_id = p.player_id
JOIN teams t ON ss.team_id = t.team_id
JOIN season_competitions sc ON ss.season_competition_id = sc.season_competition_id
JOIN seasons s ON sc.season_id = s.season_id
JOIN competitions c ON sc.competition_id = c.competition_id
WHERE t.team_id = 1
LIMIT 10;
```

---

## Rollback Plan

If any migration fails:

```sql
-- Rollback Phase 1 (unique constraints)
DROP INDEX IF EXISTS idx_cards_unique_event;
DROP INDEX IF EXISTS idx_goals_unique_event;
DROP INDEX IF EXISTS idx_lineups_unique_entry;
DROP INDEX IF EXISTS idx_substitutions_unique_event;

-- Rollback Phase 2 (foreign keys)
ALTER TABLE player_careers DROP COLUMN IF EXISTS team_id;
ALTER TABLE season_squads DROP COLUMN IF EXISTS team_id;
```

---

## Success Criteria

✅ **Phase 1 Complete When:**
- All 4 unique constraints are in place
- No duplicate events can be inserted
- Existing data remains intact

✅ **Phase 2 Complete When:**
- `player_careers` has optional `team_id` FK
- `season_squads` has required `team_id` FK
- Can join both tables with `teams` table
- All existing FSV Mainz 05 careers have `team_id = 1`

✅ **Phase 3 Complete When:**
- Parser updated with all Mainz historical names
- Parser inserts `team_id` for season_squads
- Parser inserts `team_id` for player_careers (when known)
- Test re-parse of one season succeeds

---

## Next Steps After Schema Fix

1. **Run full database re-parse** with updated parser
2. **Verify data quality** (no duplicates, correct team associations)
3. **Update documentation** to match actual schema
4. **Then and only then** - proceed with performance optimizations

---

**Decision:** Let's implement Phase 1 (unique constraints) immediately, then test before proceeding to Phase 2.
