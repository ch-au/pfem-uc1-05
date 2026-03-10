-- ============================================================================
-- MIGRATION 007: Create Performance-Optimized Materialized Views
-- ============================================================================
-- Purpose: Create materialized views for common, expensive queries
-- Date: 2025-11-09
--
-- Prerequisites:
--   - Migration 004: Unique constraints (prevents duplicates)
--   - Migration 005: Team foreign keys (enables joins)
--   - Migration 006: Merged duplicate Mainz teams (team_id = 1)
--
-- This migration creates materialized views that cache results of
-- commonly-used expensive queries involving multiple JOINs and aggregations.
--
-- Views created:
--   1. mainz_match_results - All Mainz matches with detailed info
--   2. player_career_stats - Player statistics aggregated
--   3. season_performance - Season-by-season Mainz performance
--   4. competition_statistics - Win/loss stats by competition
--
-- ============================================================================

-- ============================================================================
-- VIEW 1: Mainz Match Results (Comprehensive Match Data)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mainz_match_results AS
SELECT
    m.match_id,
    m.match_date,
    s.label as season,
    s.start_year,
    s.end_year,
    c.name as competition,
    c.level as competition_level,
    m.round_name,
    m.matchday,
    -- Team info
    t_home.name as home_team,
    t_away.name as away_team,
    -- Score
    m.home_score,
    m.away_score,
    m.halftime_home,
    m.halftime_away,
    -- Mainz perspective
    CASE WHEN m.home_team_id = 1 THEN 'Home' ELSE 'Away' END as mainz_location,
    CASE WHEN m.home_team_id = 1 THEN m.home_score ELSE m.away_score END as mainz_score,
    CASE WHEN m.home_team_id = 1 THEN m.away_score ELSE m.home_score END as opponent_score,
    -- Result from Mainz perspective
    CASE
        WHEN m.home_team_id = 1 AND m.home_score > m.away_score THEN 'W'
        WHEN m.away_team_id = 1 AND m.away_score > m.home_score THEN 'W'
        WHEN m.home_score = m.away_score THEN 'D'
        ELSE 'L'
    END as result,
    -- Additional match info
    m.venue,
    m.attendance,
    r.name as referee,
    -- Goal scorers for Mainz (JSON)
    (SELECT json_agg(json_build_object(
        'player', p.name,
        'minute', g.minute,
        'stoppage', g.stoppage,
        'type', g.event_type
    ))
     FROM goals g
     JOIN players p ON g.player_id = p.player_id
     WHERE g.match_id = m.match_id
       AND g.team_id = 1
       AND (g.event_type IS NULL OR g.event_type != 'own_goal')
    ) as mainz_scorers,
    -- Cards for Mainz players (JSON)
    (SELECT json_agg(json_build_object(
        'player', p.name,
        'minute', ca.minute,
        'type', ca.card_type
    ))
     FROM cards ca
     JOIN players p ON ca.player_id = p.player_id
     WHERE ca.match_id = m.match_id
       AND ca.team_id = 1
    ) as mainz_cards
FROM matches m
JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN seasons s ON sc.season_id = s.season_id
JOIN competitions c ON sc.competition_id = c.competition_id
JOIN teams t_home ON m.home_team_id = t_home.team_id
JOIN teams t_away ON m.away_team_id = t_away.team_id
LEFT JOIN referees r ON m.referee_id = r.referee_id
WHERE m.home_team_id = 1 OR m.away_team_id = 1
ORDER BY m.match_date DESC;

-- Indexes on mainz_match_results
CREATE UNIQUE INDEX IF NOT EXISTS idx_mainz_match_results_match_id
ON mainz_match_results(match_id);

CREATE INDEX IF NOT EXISTS idx_mainz_match_results_date
ON mainz_match_results(match_date DESC);

CREATE INDEX IF NOT EXISTS idx_mainz_match_results_season
ON mainz_match_results(season);

CREATE INDEX IF NOT EXISTS idx_mainz_match_results_competition
ON mainz_match_results(competition);

CREATE INDEX IF NOT EXISTS idx_mainz_match_results_result
ON mainz_match_results(result);

COMMENT ON MATERIALIZED VIEW mainz_match_results IS
'All Mainz 05 matches with comprehensive details. Refresh daily or after importing new matches.';

-- ============================================================================
-- VIEW 2: Player Career Stats (Aggregated Player Performance)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS player_career_stats AS
SELECT
    p.player_id,
    p.name,
    p.nationality,
    p.primary_position,
    p.birth_date,
    p.height_cm,
    p.weight_kg,
    -- Appearance stats
    COUNT(DISTINCT ml.match_id) as total_appearances,
    COUNT(DISTINCT CASE WHEN ml.is_starter THEN ml.match_id END) as total_starts,
    COUNT(DISTINCT CASE WHEN NOT ml.is_starter THEN ml.match_id END) as total_sub_appearances,
    -- Goal stats
    COUNT(DISTINCT g.goal_id) as total_goals,
    COUNT(DISTINCT CASE WHEN g.event_type = 'penalty' THEN g.goal_id END) as penalty_goals,
    COUNT(DISTINCT CASE WHEN g.event_type IS NULL OR g.event_type NOT IN ('penalty', 'own_goal')
                   THEN g.goal_id END) as open_play_goals,
    -- Assist stats
    COUNT(DISTINCT ga.goal_id) as total_assists,
    -- Card stats
    COUNT(DISTINCT CASE WHEN ca.card_type = 'yellow' THEN ca.card_id END) as yellow_cards,
    COUNT(DISTINCT CASE WHEN ca.card_type = 'second_yellow' THEN ca.card_id END) as second_yellow_cards,
    COUNT(DISTINCT CASE WHEN ca.card_type = 'red' THEN ca.card_id END) as red_cards,
    -- Career span
    MIN(m.match_date) as first_match,
    MAX(m.match_date) as last_match,
    -- Goals per match ratio
    ROUND(
        COUNT(DISTINCT g.goal_id)::numeric / NULLIF(COUNT(DISTINCT ml.match_id), 0),
        3
    ) as goals_per_match
FROM players p
LEFT JOIN match_lineups ml ON p.player_id = ml.player_id AND ml.team_id = 1
LEFT JOIN goals g ON p.player_id = g.player_id AND g.team_id = 1
    AND (g.event_type IS NULL OR g.event_type != 'own_goal')
LEFT JOIN goals ga ON p.player_id = ga.assist_player_id AND ga.team_id = 1
LEFT JOIN cards ca ON p.player_id = ca.player_id AND ca.team_id = 1
LEFT JOIN matches m ON ml.match_id = m.match_id
GROUP BY p.player_id, p.name, p.nationality, p.primary_position,
         p.birth_date, p.height_cm, p.weight_kg
HAVING COUNT(DISTINCT ml.match_id) > 0
ORDER BY total_goals DESC, total_appearances DESC;

-- Indexes on player_career_stats
CREATE UNIQUE INDEX IF NOT EXISTS idx_player_career_stats_player_id
ON player_career_stats(player_id);

CREATE INDEX IF NOT EXISTS idx_player_career_stats_goals
ON player_career_stats(total_goals DESC);

CREATE INDEX IF NOT EXISTS idx_player_career_stats_appearances
ON player_career_stats(total_appearances DESC);

CREATE INDEX IF NOT EXISTS idx_player_career_stats_name
ON player_career_stats(name);

COMMENT ON MATERIALIZED VIEW player_career_stats IS
'Aggregated player statistics for all Mainz 05 players. Refresh weekly or after match imports.';

-- ============================================================================
-- VIEW 3: Season Performance (Season-by-Season Statistics)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS season_performance AS
SELECT
    s.label as season,
    s.start_year,
    s.end_year,
    c.name as competition,
    -- Match counts
    COUNT(DISTINCT m.match_id) as matches_played,
    -- Results
    SUM(CASE
        WHEN (m.home_team_id = 1 AND m.home_score > m.away_score) OR
             (m.away_team_id = 1 AND m.away_score > m.home_score)
        THEN 1 ELSE 0
    END) as wins,
    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) as draws,
    SUM(CASE
        WHEN (m.home_team_id = 1 AND m.home_score < m.away_score) OR
             (m.away_team_id = 1 AND m.away_score < m.home_score)
        THEN 1 ELSE 0
    END) as losses,
    -- Goals
    SUM(CASE WHEN m.home_team_id = 1 THEN m.home_score ELSE m.away_score END) as goals_for,
    SUM(CASE WHEN m.home_team_id = 1 THEN m.away_score ELSE m.home_score END) as goals_against,
    SUM(CASE WHEN m.home_team_id = 1 THEN m.home_score ELSE m.away_score END) -
    SUM(CASE WHEN m.home_team_id = 1 THEN m.away_score ELSE m.home_score END) as goal_difference,
    -- Win percentage
    ROUND(
        100.0 * SUM(CASE
            WHEN (m.home_team_id = 1 AND m.home_score > m.away_score) OR
                 (m.away_team_id = 1 AND m.away_score > m.home_score)
            THEN 1 ELSE 0
        END) / NULLIF(COUNT(DISTINCT m.match_id), 0),
        1
    ) as win_percentage
FROM seasons s
JOIN season_competitions sc ON s.season_id = sc.season_id
JOIN competitions c ON sc.competition_id = c.competition_id
JOIN matches m ON sc.season_competition_id = m.season_competition_id
WHERE m.home_team_id = 1 OR m.away_team_id = 1
GROUP BY s.season_id, s.label, s.start_year, s.end_year, c.competition_id, c.name
ORDER BY s.start_year DESC, c.name;

-- Indexes on season_performance
CREATE INDEX IF NOT EXISTS idx_season_performance_season
ON season_performance(season);

CREATE INDEX IF NOT EXISTS idx_season_performance_competition
ON season_performance(competition);

CREATE INDEX IF NOT EXISTS idx_season_performance_year
ON season_performance(start_year DESC);

COMMENT ON MATERIALIZED VIEW season_performance IS
'Season-by-season performance statistics for each competition. Refresh after season ends or match imports.';

-- ============================================================================
-- VIEW 4: Competition Statistics (All-Time by Competition)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS competition_statistics AS
SELECT
    c.name as competition,
    c.level as competition_level,
    -- Participation
    COUNT(DISTINCT s.season_id) as seasons_participated,
    MIN(s.start_year) as first_season,
    MAX(s.end_year) as last_season,
    -- Match counts
    COUNT(DISTINCT m.match_id) as total_matches,
    -- Results
    SUM(CASE
        WHEN (m.home_team_id = 1 AND m.home_score > m.away_score) OR
             (m.away_team_id = 1 AND m.away_score > m.home_score)
        THEN 1 ELSE 0
    END) as wins,
    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) as draws,
    SUM(CASE
        WHEN (m.home_team_id = 1 AND m.home_score < m.away_score) OR
             (m.away_team_id = 1 AND m.away_score < m.home_score)
        THEN 1 ELSE 0
    END) as losses,
    -- Goals
    SUM(CASE WHEN m.home_team_id = 1 THEN m.home_score ELSE m.away_score END) as goals_for,
    SUM(CASE WHEN m.home_team_id = 1 THEN m.away_score ELSE m.home_score END) as goals_against,
    -- Win percentage
    ROUND(
        100.0 * SUM(CASE
            WHEN (m.home_team_id = 1 AND m.home_score > m.away_score) OR
                 (m.away_team_id = 1 AND m.away_score > m.home_score)
            THEN 1 ELSE 0
        END) / NULLIF(COUNT(DISTINCT m.match_id), 0),
        1
    ) as win_percentage
FROM competitions c
JOIN season_competitions sc ON c.competition_id = sc.competition_id
JOIN seasons s ON sc.season_id = s.season_id
JOIN matches m ON sc.season_competition_id = m.season_competition_id
WHERE m.home_team_id = 1 OR m.away_team_id = 1
GROUP BY c.competition_id, c.name, c.level
ORDER BY total_matches DESC;

-- Indexes on competition_statistics
CREATE UNIQUE INDEX IF NOT EXISTS idx_competition_statistics_competition
ON competition_statistics(competition);

CREATE INDEX IF NOT EXISTS idx_competition_statistics_matches
ON competition_statistics(total_matches DESC);

COMMENT ON MATERIALIZED VIEW competition_statistics IS
'All-time statistics by competition. Refresh monthly or after significant data imports.';

-- ============================================================================
-- PART 5: REFRESH FUNCTIONS
-- ============================================================================

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
RETURNS TABLE(view_name TEXT, refresh_time INTERVAL) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
BEGIN
    -- Refresh mainz_match_results
    start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;
    end_time := clock_timestamp();
    view_name := 'mainz_match_results';
    refresh_time := end_time - start_time;
    RETURN NEXT;

    -- Refresh player_career_stats
    start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY player_career_stats;
    end_time := clock_timestamp();
    view_name := 'player_career_stats';
    refresh_time := end_time - start_time;
    RETURN NEXT;

    -- Refresh season_performance
    start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY season_performance;
    end_time := clock_timestamp();
    view_name := 'season_performance';
    refresh_time := end_time - start_time;
    RETURN NEXT;

    -- Refresh competition_statistics
    start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY competition_statistics;
    end_time := clock_timestamp();
    view_name := 'competition_statistics';
    refresh_time := end_time - start_time;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_all_materialized_views() IS
'Refreshes all materialized views and returns timing for each. Usage: SELECT * FROM refresh_all_materialized_views();';

-- ============================================================================
-- PART 6: ANALYZE TABLES
-- ============================================================================

ANALYZE mainz_match_results;
ANALYZE player_career_stats;
ANALYZE season_performance;
ANALYZE competition_statistics;

-- ============================================================================
-- SUMMARY
-- ============================================================================
--
-- Materialized Views Created:
--   ✓ mainz_match_results - All Mainz matches with details
--   ✓ player_career_stats - Player statistics aggregated
--   ✓ season_performance - Season-by-season performance
--   ✓ competition_statistics - All-time stats by competition
--
-- Indexes Created: 13 total
--   ✓ Unique indexes on primary keys
--   ✓ Indexes on commonly filtered/sorted columns
--
-- Functions Created:
--   ✓ refresh_all_materialized_views() - Refresh all views with timing
--
-- Usage Examples:
--   -- Query recent matches
--   SELECT * FROM mainz_match_results WHERE season = '2023-24';
--
--   -- Top scorers of all time
--   SELECT name, total_goals, total_appearances
--   FROM player_career_stats
--   ORDER BY total_goals DESC LIMIT 10;
--
--   -- Bundesliga performance by season
--   SELECT season, wins, draws, losses, win_percentage
--   FROM season_performance
--   WHERE competition = 'Bundesliga'
--   ORDER BY start_year DESC;
--
--   -- Competition win rates
--   SELECT competition, total_matches, win_percentage
--   FROM competition_statistics
--   ORDER BY total_matches DESC;
--
--   -- Refresh all views
--   SELECT * FROM refresh_all_materialized_views();
--
-- Refresh Schedule Recommendations:
--   - mainz_match_results: After each match import (or daily)
--   - player_career_stats: Weekly or after match imports
--   - season_performance: After each match or end of season
--   - competition_statistics: Monthly or after significant imports
--
-- ============================================================================
