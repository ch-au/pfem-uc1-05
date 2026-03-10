-- ============================================================================
-- MIGRATION 005: Add team_id Foreign Keys for Better Joins
-- ============================================================================
-- Purpose: Enable easy joins between player_careers, season_squads, and teams
-- Date: 2025-11-09
--
-- This migration adds team_id foreign keys to tables that currently lack them:
-- - player_careers: Add optional team_id (keeps team_name for external clubs)
-- - season_squads: Add required team_id (defaults to FSV Mainz 05)
--
-- Benefits:
-- - Enables direct joins with teams table
-- - Improves query performance
-- - Maintains data normalization
-- - Keeps flexibility for external/unknown teams
-- ============================================================================

-- ============================================================================
-- PART 1: ADD TEAM_ID TO PLAYER_CAREERS (Optional FK)
-- ============================================================================

-- Add optional team_id column
-- Keeps team_name for flexibility with external clubs not in teams table
ALTER TABLE player_careers
ADD COLUMN IF NOT EXISTS team_id INTEGER;

-- Add foreign key constraint
ALTER TABLE player_careers
ADD CONSTRAINT fk_player_careers_team
FOREIGN KEY (team_id) REFERENCES teams(team_id)
ON DELETE SET NULL;

-- Backfill team_id for known teams using exact name match
UPDATE player_careers pc
SET team_id = t.team_id
FROM teams t
WHERE pc.team_id IS NULL
  AND LOWER(TRIM(pc.team_name)) = LOWER(t.name);

-- Backfill using normalized name match for remaining records
UPDATE player_careers pc
SET team_id = t.team_id
FROM teams t
WHERE pc.team_id IS NULL
  AND LOWER(TRIM(pc.team_name)) = t.normalized_name;

-- Add indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_player_careers_team
ON player_careers(team_id)
WHERE team_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_player_careers_player_team
ON player_careers(player_id, team_id)
WHERE team_id IS NOT NULL;

COMMENT ON COLUMN player_careers.team_id IS
'Foreign key to teams table. NULL for external clubs not in teams table. Use team_name for those cases.';

-- ============================================================================
-- PART 2: ADD TEAM_ID TO SEASON_SQUADS (Required FK)
-- ============================================================================

-- Add team_id column with default to FSV Mainz 05 (team_id = 1)
-- This is safe because historically all season_squads entries are for FSV Mainz 05
ALTER TABLE season_squads
ADD COLUMN IF NOT EXISTS team_id INTEGER DEFAULT 1;

-- Update existing records explicitly (makes migration clear)
UPDATE season_squads
SET team_id = 1
WHERE team_id IS NULL OR team_id = 1;

-- Remove default for future inserts (force explicit team_id)
ALTER TABLE season_squads
ALTER COLUMN team_id DROP DEFAULT;

-- Make it NOT NULL
ALTER TABLE season_squads
ALTER COLUMN team_id SET NOT NULL;

-- Add foreign key constraint
ALTER TABLE season_squads
ADD CONSTRAINT fk_season_squads_team
FOREIGN KEY (team_id) REFERENCES teams(team_id)
ON DELETE CASCADE;

-- Add indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_season_squads_team
ON season_squads(team_id);

CREATE INDEX IF NOT EXISTS idx_season_squads_season_team
ON season_squads(season_competition_id, team_id);

CREATE INDEX IF NOT EXISTS idx_season_squads_player_team
ON season_squads(player_id, team_id);

COMMENT ON COLUMN season_squads.team_id IS
'Foreign key to teams table. References the team this squad belongs to. Historically all FSV Mainz 05 (team_id=1).';

-- ============================================================================
-- PART 3: UPDATE STATISTICS
-- ============================================================================

ANALYZE public.player_careers;
ANALYZE public.season_squads;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check backfill success for player_careers
-- Shows how many careers are linked vs. external clubs

/*
SELECT
    CASE
        WHEN team_id IS NOT NULL THEN 'Linked to teams table'
        ELSE 'External club (team_name only)'
    END as status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM player_careers
GROUP BY (team_id IS NOT NULL)
ORDER BY count DESC;

-- Check season_squads team distribution
SELECT
    t.name as team,
    COUNT(ss.*) as squad_entries
FROM season_squads ss
JOIN teams t ON ss.team_id = t.team_id
GROUP BY t.name
ORDER BY squad_entries DESC;

-- Verify FSV Mainz 05 careers can be joined
SELECT
    p.name as player,
    t.name as team,
    pc.start_year,
    pc.end_year
FROM player_careers pc
JOIN players p ON pc.player_id = p.player_id
JOIN teams t ON pc.team_id = t.team_id
WHERE t.team_id = 1
LIMIT 10;
*/

-- ============================================================================
-- SUMMARY
-- ============================================================================
--
-- Changes Made:
--   ✓ player_careers.team_id added (optional FK, backfilled where possible)
--   ✓ season_squads.team_id added (required FK, all set to FSV Mainz 05)
--   ✓ Foreign key constraints added
--   ✓ 5 new indexes for performance
--
-- Benefits:
--   ✓ Can now JOIN player_careers with teams table
--   ✓ Can now JOIN season_squads with teams table
--   ✓ Better data normalization
--   ✓ Faster queries with new indexes
--   ✓ Maintains flexibility for external clubs
--
-- Next Steps:
--   1. Update parser to insert team_id for new records
--   2. Verify joins work as expected (run verification queries)
--   3. Update documentation to reflect schema changes
--
-- ============================================================================
