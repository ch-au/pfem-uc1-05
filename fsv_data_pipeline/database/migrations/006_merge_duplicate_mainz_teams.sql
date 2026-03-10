-- ============================================================================
-- MIGRATION 006: Merge Duplicate Mainz 05 Team Entries
-- ============================================================================
-- Purpose: Consolidate "FSV" (team_id=31) and "1. FSV Mainz 05" (team_id=1)
-- Date: 2025-11-09
--
-- Issue: Parser created two separate teams for Mainz 05:
--   - team_id = 1:  "1. FSV Mainz 05" (historical matches)
--   - team_id = 31: "FSV" (modern Bundesliga matches)
--
-- This migration merges them into a single team (team_id = 1).
--
-- Impact:
--   - 255 matches currently use team_id = 1
--   - 3,099 matches currently use team_id = 31
--   - Total: 3,354 matches will all use team_id = 1 after migration
--
-- ============================================================================

-- ============================================================================
-- PART 1: VERIFY THE DUPLICATE TEAMS EXIST
-- ============================================================================

-- This should show both teams:
-- SELECT team_id, name FROM teams WHERE team_id IN (1, 31);
-- Expected:
--   1  | 1. FSV Mainz 05
--   31 | FSV

-- ============================================================================
-- PART 2: UPDATE ALL FOREIGN KEY REFERENCES
-- ============================================================================

-- Update matches (home team)
UPDATE matches
SET home_team_id = 1
WHERE home_team_id = 31;

-- Update matches (away team)
UPDATE matches
SET away_team_id = 1
WHERE away_team_id = 31;

-- Update goals
UPDATE goals
SET team_id = 1
WHERE team_id = 31;

-- Update cards
UPDATE cards
SET team_id = 1
WHERE team_id = 31;

-- Update match_lineups
UPDATE match_lineups
SET team_id = 1
WHERE team_id = 31;

-- Update match_substitutions
UPDATE match_substitutions
SET team_id = 1
WHERE team_id = 31;

-- Update match_coaches
UPDATE match_coaches
SET team_id = 1
WHERE team_id = 31;

-- Update season_squads (from migration 005)
UPDATE season_squads
SET team_id = 1
WHERE team_id = 31;

-- Update player_careers (from migration 005)
UPDATE player_careers
SET team_id = 1
WHERE team_id = 31;

-- Update seasons (if any reference team_id 31)
UPDATE seasons
SET team_id = 1
WHERE team_id = 31;

-- ============================================================================
-- PART 3: DELETE THE DUPLICATE TEAM ENTRY
-- ============================================================================

-- Now that all references point to team_id = 1, delete team_id = 31
DELETE FROM teams WHERE team_id = 31;

-- ============================================================================
-- PART 4: UPDATE TEAM NAME TO CANONICAL FORM
-- ============================================================================

-- Update team_id = 1 to use the modern, official name
UPDATE teams
SET name = '1. FSV Mainz 05',
    normalized_name = '1 fsv mainz 05'
WHERE team_id = 1;

-- ============================================================================
-- PART 5: VERIFY CONSOLIDATION
-- ============================================================================

-- Check that all matches now use team_id = 1
-- SELECT COUNT(*) FROM matches WHERE home_team_id = 1 OR away_team_id = 1;
-- Expected: 3,354 (255 + 3,099)

-- Check that team_id = 31 no longer exists
-- SELECT COUNT(*) FROM teams WHERE team_id = 31;
-- Expected: 0

-- ============================================================================
-- PART 6: ANALYZE TABLES
-- ============================================================================

ANALYZE matches;
ANALYZE goals;
ANALYZE cards;
ANALYZE match_lineups;
ANALYZE match_substitutions;
ANALYZE teams;

-- ============================================================================
-- SUMMARY
-- ============================================================================
--
-- Before Migration:
--   ❌ team_id = 1:  "1. FSV Mainz 05" - 255 matches
--   ❌ team_id = 31: "FSV" - 3,099 matches
--   ❌ Total teams: 2 (duplicates)
--   ❌ Queries must filter for BOTH team IDs
--
-- After Migration:
--   ✅ team_id = 1: "1. FSV Mainz 05" - 3,354 matches
--   ✅ Total teams: 1 (consolidated)
--   ✅ Queries only need to filter for team_id = 1
--
-- Benefits:
--   ✅ Data integrity restored
--   ✅ Simpler queries (single team_id)
--   ✅ Accurate statistics
--   ✅ No missing Bundesliga data
--
-- Rollback:
--   This migration cannot be easily rolled back because we don't know
--   which original records used team_id = 31 vs team_id = 1.
--   Keep a backup before running!
--
-- ============================================================================
