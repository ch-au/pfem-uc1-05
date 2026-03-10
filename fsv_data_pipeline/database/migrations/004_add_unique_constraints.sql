-- ============================================================================
-- MIGRATION 004: Add Unique Constraints for Data Integrity
-- ============================================================================
-- Purpose: Prevent duplicate events in cards, goals, lineups, substitutions
-- Date: 2025-11-09
--
-- This enforces the duplicate prevention logic already in the parser:
-- - Lines 1028-1043: Card duplicate checking
-- - Lines 976-984: Goal duplicate checking
-- - Lines 888-894: Lineup duplicate checking
-- - Lines 936-942: Substitution duplicate checking
--
-- These constraints ensure data integrity at the database level.
-- ============================================================================

-- ============================================================================
-- PART 1: CARDS - Prevent Duplicate Card Events
-- ============================================================================

-- Parser checks: (match_id, player_id, minute, card_type)
-- Special handling: 94.5% of cards have NULL minute
-- Uses COALESCE to handle NULL minutes and stoppages

CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_unique_event
ON public.cards (match_id, player_id, COALESCE(minute, -1), COALESCE(stoppage, 0), card_type);

COMMENT ON INDEX idx_cards_unique_event IS
'Prevents duplicate card events. Matches parser logic at lines 1028-1043. Uses COALESCE for NULL handling.';

-- ============================================================================
-- PART 2: GOALS - Prevent Duplicate Goals
-- ============================================================================

-- Parser checks: (match_id, player_id, minute, stoppage)
-- Special handling: player_id can be NULL for own goals
-- Uses COALESCE to handle NULL player_id and stoppage

CREATE UNIQUE INDEX IF NOT EXISTS idx_goals_unique_event
ON public.goals (match_id, COALESCE(player_id, -1), minute, COALESCE(stoppage, 0));

COMMENT ON INDEX idx_goals_unique_event IS
'Prevents duplicate goal events. Matches parser logic at lines 976-984. Handles NULL player_id for own goals.';

-- ============================================================================
-- PART 3: MATCH LINEUPS - Prevent Duplicate Lineup Entries
-- ============================================================================

-- Parser checks: (match_id, player_id, team_id)
-- A player can only appear once per match per team

CREATE UNIQUE INDEX IF NOT EXISTS idx_lineups_unique_entry
ON public.match_lineups (match_id, player_id, team_id);

COMMENT ON INDEX idx_lineups_unique_entry IS
'Prevents duplicate lineup entries. Matches parser logic at lines 888-894. One entry per player per match per team.';

-- ============================================================================
-- PART 4: SUBSTITUTIONS - Prevent Duplicate Substitutions
-- ============================================================================

-- Parser checks: (match_id, player_on_id, player_off_id, minute, stoppage)
-- Uses COALESCE for NULL stoppage

CREATE UNIQUE INDEX IF NOT EXISTS idx_substitutions_unique_event
ON public.match_substitutions (match_id, player_on_id, player_off_id, minute, COALESCE(stoppage, -1));

COMMENT ON INDEX idx_substitutions_unique_event IS
'Prevents duplicate substitution events. Matches parser logic at lines 936-942. Uses COALESCE for NULL stoppage.';

-- ============================================================================
-- PART 5: UPDATE STATISTICS
-- ============================================================================

-- Update statistics for better query planning
ANALYZE public.cards;
ANALYZE public.goals;
ANALYZE public.match_lineups;
ANALYZE public.match_substitutions;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check for any existing violations (should return 0 for all)
-- Uncomment to run verification:

/*
-- Check cards duplicates
SELECT COUNT(*) - COUNT(DISTINCT (match_id, player_id, COALESCE(minute, -1), COALESCE(stoppage, 0), card_type))
FROM public.cards;

-- Check goals duplicates
SELECT COUNT(*) - COUNT(DISTINCT (match_id, COALESCE(player_id, -1), minute, COALESCE(stoppage, 0)))
FROM public.goals;

-- Check lineups duplicates
SELECT COUNT(*) - COUNT(DISTINCT (match_id, player_id, team_id))
FROM public.match_lineups;

-- Check substitutions duplicates
SELECT COUNT(*) - COUNT(DISTINCT (match_id, player_on_id, player_off_id, minute, COALESCE(stoppage, -1)))
FROM public.match_substitutions;
*/

-- ============================================================================
-- SUMMARY
-- ============================================================================
--
-- Constraints Added:
--   ✓ idx_cards_unique_event (prevents duplicate cards)
--   ✓ idx_goals_unique_event (prevents duplicate goals)
--   ✓ idx_lineups_unique_entry (prevents duplicate lineups)
--   ✓ idx_substitutions_unique_event (prevents duplicate substitutions)
--
-- Benefits:
--   ✓ Database-level data integrity
--   ✓ Matches parser's duplicate prevention logic
--   ✓ Prevents future data quality issues
--   ✓ Enables reliable aggregation queries
--
-- Next Steps:
--   1. Verify no existing duplicates (run verification queries above)
--   2. Test constraint enforcement with sample inserts
--   3. Proceed to Migration 005: Add team_id foreign keys
--
-- ============================================================================
