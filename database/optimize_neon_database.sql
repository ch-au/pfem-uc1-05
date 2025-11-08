-- ============================================================================
-- NEON DATABASE OPTIMIZATION: Indexes & Materialized Views
-- ============================================================================
-- Purpose: Optimize database performance for chatbot and SQL agent queries
-- Target: Neon PostgreSQL Cloud Database
-- Date: 2025-01-XX
--
-- Usage:
--   psql $DB_URL -f optimize_neon_database.sql
--   OR via Python: python optimize_neon_database.py
-- ============================================================================

-- ============================================================================
-- PART 1: CHAT TABLES OPTIMIZATION
-- ============================================================================
-- These tables are frequently queried by the chatbot service

-- Composite index for chat_messages: session_id + created_at DESC
-- This speeds up: SELECT ... FROM chat_messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?
-- Used by: chatbot_service.get_session_history()
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created_desc 
ON public.chat_messages(session_id, created_at DESC);

-- Index for cleaning up expired sessions
-- Used by: Session cleanup queries
CREATE INDEX IF NOT EXISTS idx_chat_sessions_expires_at 
ON public.chat_sessions(expires_at) 
WHERE expires_at < CURRENT_TIMESTAMP;

-- Index for chat_sessions updated_at (for session activity tracking)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at 
ON public.chat_sessions(updated_at DESC);

-- Partial index for active chat sessions (not expired)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_active 
ON public.chat_sessions(session_id, updated_at DESC) 
WHERE expires_at >= CURRENT_TIMESTAMP;

-- Covering index for chat_messages: includes content for fast retrieval
-- This can speed up queries that only need role and content
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_role_created 
ON public.chat_messages(session_id, role, created_at DESC) 
INCLUDE (content);

-- ============================================================================
-- PART 2: FOOTBALL DATABASE INDEXES
-- ============================================================================
-- Additional indexes for common SQL agent query patterns

-- Composite index for player name lookups (case-insensitive searches)
-- Speeds up: WHERE name ILIKE '%search%'
CREATE INDEX IF NOT EXISTS idx_players_name_trgm 
ON public.players USING gin(name gin_trgm_ops);

-- Composite index for team name lookups
CREATE INDEX IF NOT EXISTS idx_teams_name_trgm 
ON public.teams USING gin(name gin_trgm_ops);

-- Enable pg_trgm extension if not already enabled
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Index for goals by player and event type (for penalty/own goal queries)
CREATE INDEX IF NOT EXISTS idx_goals_player_event_type 
ON public.goals(player_id, event_type) 
WHERE event_type IS NOT NULL;

-- Composite index for match queries with date range
-- Speeds up: WHERE match_date BETWEEN ? AND ?
CREATE INDEX IF NOT EXISTS idx_matches_date_range 
ON public.matches(match_date) 
INCLUDE (home_team_id, away_team_id, home_score, away_score);

-- Index for match_lineups by team and is_starter
-- Speeds up: WHERE team_id = ? AND is_starter = true
CREATE INDEX IF NOT EXISTS idx_lineups_team_starter 
ON public.match_lineups(team_id, is_starter) 
WHERE is_starter = true;

-- Composite index for cards by player and match (for player card stats)
CREATE INDEX IF NOT EXISTS idx_cards_player_match_type 
ON public.cards(player_id, match_id, card_type);

-- Index for season_competitions lookups
CREATE INDEX IF NOT EXISTS idx_season_competitions_both_ids 
ON public.season_competitions(season_id, competition_id);

-- ============================================================================
-- PART 3: MATERIALIZED VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Materialized view: Top scorers (for quick "who scored most goals" queries)
CREATE MATERIALIZED VIEW IF NOT EXISTS public.top_scorers AS
SELECT 
    p.player_id,
    p.name,
    p.nationality,
    p.primary_position,
    COUNT(DISTINCT g.goal_id) as total_goals,
    COUNT(DISTINCT CASE WHEN g.event_type = 'penalty' THEN g.goal_id END) as penalty_goals,
    COUNT(DISTINCT CASE WHEN g.event_type IS NULL THEN g.goal_id END) as regular_goals,
    COUNT(DISTINCT ml.match_id) as appearances,
    ROUND(
        COUNT(DISTINCT g.goal_id)::numeric / NULLIF(COUNT(DISTINCT ml.match_id), 0),
        3
    ) as goals_per_game,
    MIN(m.match_date) as first_goal_date,
    MAX(m.match_date) as last_goal_date
FROM public.players p
LEFT JOIN public.goals g ON p.player_id = g.player_id 
    AND g.team_id = 1  -- Only FSV Mainz goals
    AND (g.event_type IS NULL OR g.event_type != 'own_goal')
LEFT JOIN public.matches m ON g.match_id = m.match_id
LEFT JOIN public.match_lineups ml ON p.player_id = ml.player_id 
    AND ml.team_id = 1
GROUP BY p.player_id, p.name, p.nationality, p.primary_position
HAVING COUNT(DISTINCT g.goal_id) > 0
WITH DATA;

-- Indexes on top_scorers
CREATE UNIQUE INDEX IF NOT EXISTS idx_top_scorers_player_id 
ON public.top_scorers(player_id);

CREATE INDEX IF NOT EXISTS idx_top_scorers_total_goals 
ON public.top_scorers(total_goals DESC);

-- Materialized view: Match results summary (for quick match lookup)
CREATE MATERIALIZED VIEW IF NOT EXISTS public.match_results_summary AS
SELECT 
    m.match_id,
    m.match_date,
    s.label as season,
    c.name as competition,
    t_home.name as home_team,
    t_away.name as away_team,
    m.home_score,
    m.away_score,
    CASE 
        WHEN m.home_team_id = 1 THEN 'Home'
        WHEN m.away_team_id = 1 THEN 'Away'
        ELSE NULL
    END as fsv_location,
    CASE 
        WHEN m.home_team_id = 1 AND m.home_score > m.away_score THEN 'Win'
        WHEN m.away_team_id = 1 AND m.away_score > m.home_score THEN 'Win'
        WHEN m.home_score = m.away_score THEN 'Draw'
        ELSE 'Loss'
    END as fsv_result,
    (SELECT COUNT(*) FROM public.goals WHERE match_id = m.match_id) as total_goals,
    (SELECT COUNT(*) FROM public.cards WHERE match_id = m.match_id) as total_cards
FROM public.matches m
JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN public.seasons s ON sc.season_id = s.season_id
JOIN public.competitions c ON sc.competition_id = c.competition_id
JOIN public.teams t_home ON m.home_team_id = t_home.team_id
JOIN public.teams t_away ON m.away_team_id = t_away.team_id
WHERE m.home_team_id = 1 OR m.away_team_id = 1
WITH DATA;

-- Indexes on match_results_summary
CREATE UNIQUE INDEX IF NOT EXISTS idx_match_results_match_id 
ON public.match_results_summary(match_id);

CREATE INDEX IF NOT EXISTS idx_match_results_date 
ON public.match_results_summary(match_date DESC);

CREATE INDEX IF NOT EXISTS idx_match_results_season 
ON public.match_results_summary(season);

CREATE INDEX IF NOT EXISTS idx_match_results_fsv_result 
ON public.match_results_summary(fsv_result);

-- Materialized view: Player appearances by season (for career stats)
CREATE MATERIALIZED VIEW IF NOT EXISTS public.player_season_stats AS
SELECT 
    p.player_id,
    p.name,
    s.label as season,
    comp.name as competition,
    COUNT(DISTINCT ml.match_id) as appearances,
    COUNT(DISTINCT CASE WHEN ml.is_starter THEN ml.match_id END) as starts,
    COUNT(DISTINCT g.goal_id) as goals,
    COUNT(DISTINCT ga.goal_id) as assists,
    COUNT(DISTINCT CASE WHEN ca.card_type = 'yellow' THEN ca.card_id END) as yellow_cards,
    COUNT(DISTINCT CASE WHEN ca.card_type = 'red' THEN ca.card_id END) as red_cards
FROM public.players p
LEFT JOIN public.match_lineups ml ON p.player_id = ml.player_id 
    AND ml.team_id = 1
LEFT JOIN public.matches m ON ml.match_id = m.match_id
LEFT JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
LEFT JOIN public.seasons s ON sc.season_id = s.season_id
LEFT JOIN public.competitions comp ON sc.competition_id = comp.competition_id
LEFT JOIN public.goals g ON p.player_id = g.player_id 
    AND g.match_id = m.match_id 
    AND g.team_id = 1
LEFT JOIN public.goals ga ON p.player_id = ga.assist_player_id 
    AND ga.match_id = m.match_id
LEFT JOIN public.cards ca ON p.player_id = ca.player_id 
    AND ca.match_id = m.match_id
GROUP BY p.player_id, p.name, s.label, comp.name
HAVING COUNT(DISTINCT ml.match_id) > 0
WITH DATA;

-- Indexes on player_season_stats
CREATE INDEX IF NOT EXISTS idx_player_season_stats_player_season 
ON public.player_season_stats(player_id, season);

CREATE INDEX IF NOT EXISTS idx_player_season_stats_goals 
ON public.player_season_stats(goals DESC);

-- ============================================================================
-- PART 4: ANALYZE & VACUUM
-- ============================================================================

-- Update statistics for better query planning
ANALYZE public.chat_sessions;
ANALYZE public.chat_messages;
ANALYZE public.matches;
ANALYZE public.players;
ANALYZE public.goals;
ANALYZE public.match_lineups;
ANALYZE public.cards;
ANALYZE public.teams;
ANALYZE public.season_competitions;

-- Vacuum to reclaim space and update statistics
VACUUM ANALYZE public.chat_sessions;
VACUUM ANALYZE public.chat_messages;
VACUUM ANALYZE public.matches;
VACUUM ANALYZE public.match_lineups;

-- ============================================================================
-- PART 5: REFRESH MATERIALIZED VIEWS
-- ============================================================================

-- Note: REFRESH MATERIALIZED VIEW commands should be run manually or via Python script
-- since PostgreSQL doesn't support "IF EXISTS" syntax for REFRESH.
-- The Python script handles existence checks before refreshing.
--
-- To refresh manually:
--   REFRESH MATERIALIZED VIEW public.player_statistics;
--   REFRESH MATERIALIZED VIEW public.match_details;
--   REFRESH MATERIALIZED VIEW public.season_summary;
--   REFRESH MATERIALIZED VIEW public.top_scorers;
--   REFRESH MATERIALIZED VIEW public.match_results_summary;
--   REFRESH MATERIALIZED VIEW public.player_season_stats;

-- ============================================================================
-- SUMMARY
-- ============================================================================
-- 
-- Indexes created:
--   ✓ Chat tables: 5 new indexes for faster chat queries
--   ✓ Football tables: 8 new indexes for common query patterns
-- 
-- Materialized views created:
--   ✓ top_scorers: Pre-computed top goal scorers
--   ✓ match_results_summary: Quick match result lookups
--   ✓ player_season_stats: Player stats per season
-- 
-- Next steps:
--   1. Monitor query performance
--   2. Refresh materialized views periodically: 
--      REFRESH MATERIALIZED VIEW public.top_scorers;
--   3. Consider setting up automatic refresh schedule
-- ============================================================================

