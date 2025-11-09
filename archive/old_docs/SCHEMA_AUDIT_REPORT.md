# Database Schema Audit Report
**Date:** 2025-11-09
**Database:** Neon PostgreSQL (FSV Mainz 05 Database)
**Audit Purpose:** Verify schema consistency before performance optimizations

---

## Executive Summary

### ✅ Good News
1. **Duplicate cards issue RESOLVED** - Previously had 48.1% duplicates, now 0%
2. **Schema documentation is comprehensive** and well-maintained
3. **Core football data is intact** - 3,231 matches, 10,094 players, proper indexes
4. **Vector embeddings are implemented** for semantic search

### ⚠️ Issues Found

1. **Missing unique constraints** - Cards table has no protection against future duplicates
2. **Schema mismatches** - Documentation doesn't match actual implementation in some areas
3. **No quiz data** - Quiz tables exist but are empty (0 games, 0 questions)
4. **Materialized views don't exist** - None of the documented/planned views are created
5. **Player_careers schema inconsistency** - Uses `team_name` (TEXT) instead of `team_id` (FK)

---

## Detailed Findings

### 1. Cards Table - Duplicate Prevention

**Status:** ⚠️ **VULNERABLE**

**Finding:**
- Current duplicates: 0 (data is clean!)
- But NO unique constraint exists to prevent future duplicates
- Documentation shows this was a major issue (48.1% duplicates in October 2025)

**Actual Schema:**
```sql
CREATE TABLE public.cards (
    card_id INTEGER PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id) ON DELETE CASCADE,
    team_id INTEGER REFERENCES teams(team_id),
    player_id INTEGER REFERENCES players(player_id),
    minute INTEGER,
    stoppage INTEGER,
    card_type TEXT
);
-- NO UNIQUE CONSTRAINT!
```

**Recommendation:**
```sql
-- Add unique constraint to prevent future duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_unique_event
ON public.cards (match_id, player_id, COALESCE(minute, -1), COALESCE(stoppage, 0), card_type);
```

---

### 2. Player Careers Table - Schema Inconsistency

**Status:** ⚠️ **INCONSISTENT**

**Finding:**
- Documentation suggests `team_id` column should exist
- Actual implementation uses `team_name TEXT` instead
- This breaks foreign key relationships and makes joins harder

**Actual Schema:**
```sql
CREATE TABLE public.player_careers (
    career_id INTEGER PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id) ON DELETE CASCADE,
    team_name TEXT NOT NULL,  -- Should be team_id INTEGER FK?
    start_year INTEGER,
    end_year INTEGER,
    notes TEXT
);
```

**Impact:**
- Cannot directly join with teams table
- Data normalization is broken
- Harder to query career statistics

**Options:**
1. Keep as-is (team_name is flexible for external teams)
2. Add optional `team_id` column for FSV-related careers
3. Full migration to `team_id` with lookup table for external teams

---

### 3. Season Squads Table - Missing Team Reference

**Status:** ⚠️ **MISSING CONTEXT**

**Finding:**
- `season_squads` table has NO `team_id` column
- Cannot distinguish between FSV and opponent squads
- Makes it hard to query "FSV squad for season X"

**Actual Schema:**
```sql
CREATE TABLE public.season_squads (
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
- Assumes all squad entries are for FSV Mainz 05
- Cannot track opponent squads
- Optimization queries that filter by `team_id = 1` will fail

---

### 4. Quiz Tables - Empty

**Status:** ℹ️  **NO DATA**

**Finding:**
- All quiz tables exist and have proper schema
- But completely empty: 0 games, 0 questions, 0 rounds, 0 answers
- Materialized view `quiz_global_leaderboard` cannot be created from empty data

**Current State:**
```
Games: 0
Questions: 0
Rounds: 0
Answers: 0
```

**Recommendation:**
- Skip quiz-related optimizations until data exists
- OR seed with sample quiz data for testing
- Focus on football data optimizations first

---

### 5. Materialized Views - None Exist

**Status:** ❌ **NOT IMPLEMENTED**

**Finding:**
- Documentation mentions several materialized views
- None actually exist in the database
- This is expected - they're part of the optimization plan

**Expected Views (from docs):**
- `top_scorers` - Not found
- `match_results_summary` - Not found
- `player_season_stats` - Not found
- `quiz_global_leaderboard` - Cannot create (no data)
- `recent_matches` - Can be created
- `player_career_highlights` - Can be created (with schema fixes)

**Recommendation:**
- Create only views that are compatible with actual schema
- Test with real data before deployment

---

## Schema vs Documentation Comparison

### ✅ Matches Documentation

| Table | Documentation | Actual | Status |
|-------|--------------|--------|--------|
| teams | ✓ | ✓ | ✅ Match |
| players | ✓ | ✓ | ✅ Match |
| coaches | ✓ | ✓ | ✅ Match |
| matches | ✓ | ✓ | ✅ Match |
| goals | ✓ | ✓ | ✅ Match |
| quiz_games | ✓ | ✓ | ✅ Match |
| quiz_questions | ✓ | ✓ | ✅ Match |

### ⚠️ Deviations from Documentation

| Table | Issue | Impact |
|-------|-------|--------|
| player_careers | Uses `team_name` not `team_id` | Cannot join with teams |
| season_squads | Missing `team_id` column | Assumes FSV-only |
| quiz_questions | No `category_id` column | Uses `topic` TEXT instead |
| cards | No unique constraint | Vulnerable to duplicates |

---

## Data Quality Summary

### ✅ Clean Data

```
Total cards: 5,768
Unique cards: 5,768
Duplicates: 0 (0.0%)  ← FIXED!
```

### 📊 Data Volume (from docs)

```
Matches: 3,231
Players: 10,094
Goals: 5,652
Cards: 5,768 (was 11,120 before deduplication)
Match Lineups: 84,172
```

---

## Index Coverage

### ✅ Good Coverage

**Current indexes: 85** (was 81 before optimization script)

Added by optimization script:
- `idx_quiz_rounds_game_round` ✅
- `idx_quiz_answers_round_player` ✅
- `idx_quiz_questions_topic_created` ✅
- `idx_quiz_games_status_created` ✅
- `idx_chat_messages_metadata` (GIN) ✅
- `idx_quiz_questions_metadata` (GIN) ✅

### ⚠️ Missing Recommended Indexes

From documentation vs actual:
- All basic indexes exist (matches, players, goals, etc.)
- Vector indexes exist (HNSW for embeddings)
- Materialized view indexes: N/A (views don't exist yet)

---

## Recommendations

### 🔴 High Priority

1. **Add unique constraint to cards table**
   ```sql
   CREATE UNIQUE INDEX idx_cards_unique_event
   ON public.cards (match_id, player_id, COALESCE(minute, -1), COALESCE(stoppage, 0), card_type);
   ```

2. **Fix materialized view definitions** to match actual schema
   - Remove references to non-existent columns (`category_id`, `team_id` in wrong tables)
   - Test views with actual data
   - Skip quiz views until data exists

3. **Document actual schema accurately**
   - Update SCHEMA_DOCUMENTATION.md with correct column names
   - Note which columns are TEXT vs FK references

### 🟡 Medium Priority

4. **Consider adding team_id to season_squads**
   - Makes squad queries more flexible
   - Enables opponent squad tracking

5. **Evaluate player_careers design**
   - Current TEXT approach is flexible but less normalized
   - Could add optional `team_id` for FSV-related entries

6. **Create baseline performance tests**
   - Measure query times before optimization
   - Document improvement metrics

### 🟢 Low Priority

7. **Seed quiz data for testing**
   - Generate sample questions
   - Test quiz leaderboard view

8. **Add CHECK constraints**
   - Validate card_type values
   - Validate difficulty levels
   - Ensure data integrity

---

## Next Steps for Optimization

### Phase 1: Fix Schema Issues (This Session)
1. ✅ Identify schema mismatches
2. ⬜ Add unique constraint to cards
3. ⬜ Create corrected materialized views (football data only)
4. ⬜ Test and verify

### Phase 2: Create Optimizations (Safe)
1. ⬜ Create `recent_matches` materialized view
2. ⬜ Create `player_career_highlights` materialized view (with schema fixes)
3. ⬜ Set up refresh functions
4. ⬜ Measure performance improvements

### Phase 3: Documentation
1. ⬜ Update schema docs with accurate column info
2. ⬜ Document optimization results
3. ⬜ Create maintenance procedures

---

## Conclusion

The database is **generally in good shape** with clean data and comprehensive coverage. The main issues are:

1. **Lack of protective constraints** (cards table)
2. **Schema documentation drift** (minor inconsistencies)
3. **Missing optimizations** (no materialized views yet)

These are all **fixable issues** that can be addressed systematically.

The optimization plan should proceed with **caution**, creating only views that match the actual schema, not the documented/assumed schema.

---

**Audit completed by:** Claude Code
**Next action:** Review with user, then proceed with safe optimizations
