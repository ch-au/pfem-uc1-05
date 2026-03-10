-- FSV Mainz 05 Archive - Materialized Views and Performance Indexes
-- Pre-computed views for common queries

-- ============================================================
-- MATERIALIZED VIEW: Player Career Statistics
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_player_career_stats CASCADE;

CREATE MATERIALIZED VIEW mv_player_career_stats AS
SELECT
    p.player_id,
    p.name,
    p.normalized_name,
    p.birth_date,
    COUNT(DISTINCT ml.match_id) as total_matches,
    COUNT(DISTINCT CASE
        WHEN (ml.team_id = m.home_team_id AND m.home_score > m.away_score)
          OR (ml.team_id = m.away_team_id AND m.away_score > m.home_score)
        THEN ml.match_id END) as wins,
    COUNT(DISTINCT CASE
        WHEN m.home_score = m.away_score
        THEN ml.match_id END) as draws,
    COUNT(DISTINCT CASE
        WHEN (ml.team_id = m.home_team_id AND m.home_score < m.away_score)
          OR (ml.team_id = m.away_team_id AND m.away_score < m.home_score)
        THEN ml.match_id END) as losses,
    COALESCE(goal_stats.goals, 0) as goals,
    COALESCE(goal_stats.assists, 0) as assists,
    COALESCE(card_stats.yellow_cards, 0) as yellow_cards,
    COALESCE(card_stats.red_cards, 0) as red_cards,
    MIN(m.match_date) as first_match,
    MAX(m.match_date) as last_match
FROM players p
LEFT JOIN match_lineups ml ON p.player_id = ml.player_id
LEFT JOIN matches m ON ml.match_id = m.match_id
LEFT JOIN (
    SELECT player_id, COUNT(*) as goals, 0 as assists
    FROM goals WHERE event_type != 'own_goal' OR event_type IS NULL
    GROUP BY player_id
    UNION ALL
    SELECT assist_player_id as player_id, 0 as goals, COUNT(*) as assists
    FROM goals WHERE assist_player_id IS NOT NULL
    GROUP BY assist_player_id
) goal_stats ON p.player_id = goal_stats.player_id
LEFT JOIN (
    SELECT player_id,
        COUNT(*) FILTER (WHERE card_type = 'yellow') as yellow_cards,
        COUNT(*) FILTER (WHERE card_type IN ('red', 'second_yellow')) as red_cards
    FROM cards
    GROUP BY player_id
) card_stats ON p.player_id = card_stats.player_id
GROUP BY p.player_id, p.name, p.normalized_name, p.birth_date,
         goal_stats.goals, goal_stats.assists, card_stats.yellow_cards, card_stats.red_cards;

CREATE UNIQUE INDEX idx_mv_player_career_player_id ON mv_player_career_stats(player_id);
CREATE INDEX idx_mv_player_career_name ON mv_player_career_stats(normalized_name);
CREATE INDEX idx_mv_player_career_matches ON mv_player_career_stats(total_matches DESC);

-- ============================================================
-- MATERIALIZED VIEW: Team Statistics
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_team_stats CASCADE;

CREATE MATERIALIZED VIEW mv_team_stats AS
SELECT
    t.team_id,
    t.name,
    t.normalized_name,
    COUNT(DISTINCT m.match_id) as total_matches,
    COUNT(DISTINCT CASE WHEN
        (m.home_team_id = t.team_id AND m.home_score > m.away_score)
        OR (m.away_team_id = t.team_id AND m.away_score > m.home_score)
    THEN m.match_id END) as wins,
    COUNT(DISTINCT CASE WHEN m.home_score = m.away_score THEN m.match_id END) as draws,
    COUNT(DISTINCT CASE WHEN
        (m.home_team_id = t.team_id AND m.home_score < m.away_score)
        OR (m.away_team_id = t.team_id AND m.away_score < m.home_score)
    THEN m.match_id END) as losses,
    SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score
             WHEN m.away_team_id = t.team_id THEN m.away_score
             ELSE 0 END) as goals_for,
    SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_score
             WHEN m.away_team_id = t.team_id THEN m.home_score
             ELSE 0 END) as goals_against,
    MIN(m.match_date) as first_match,
    MAX(m.match_date) as last_match
FROM teams t
LEFT JOIN matches m ON t.team_id = m.home_team_id OR t.team_id = m.away_team_id
GROUP BY t.team_id, t.name, t.normalized_name;

CREATE UNIQUE INDEX idx_mv_team_stats_team_id ON mv_team_stats(team_id);
CREATE INDEX idx_mv_team_stats_name ON mv_team_stats(normalized_name);

-- ============================================================
-- MATERIALIZED VIEW: Season Summary
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_season_summary CASCADE;

CREATE MATERIALIZED VIEW mv_season_summary AS
SELECT
    s.season_id,
    s.label as season,
    c.name as competition,
    c.level as competition_level,
    COUNT(m.match_id) as matches_played,
    SUM(CASE WHEN m.home_score > m.away_score THEN 1 ELSE 0 END) as home_wins,
    SUM(CASE WHEN m.away_score > m.home_score THEN 1 ELSE 0 END) as away_wins,
    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) as draws,
    SUM(m.home_score + m.away_score) as total_goals,
    MIN(m.match_date) as season_start,
    MAX(m.match_date) as season_end
FROM seasons s
JOIN season_competitions sc ON s.season_id = sc.season_id
JOIN competitions c ON sc.competition_id = c.competition_id
LEFT JOIN matches m ON sc.season_competition_id = m.season_competition_id
GROUP BY s.season_id, s.label, c.name, c.level;

CREATE INDEX idx_mv_season_summary_season ON mv_season_summary(season);
CREATE INDEX idx_mv_season_summary_competition ON mv_season_summary(competition);

-- ============================================================
-- MATERIALIZED VIEW: Coach Record
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_coach_record CASCADE;

CREATE MATERIALIZED VIEW mv_coach_record AS
SELECT
    c.coach_id,
    c.name,
    c.normalized_name,
    c.birth_date,
    COUNT(DISTINCT mc.match_id) as total_matches,
    COUNT(DISTINCT CASE
        WHEN (mc.team_id = m.home_team_id AND m.home_score > m.away_score)
          OR (mc.team_id = m.away_team_id AND m.away_score > m.home_score)
        THEN mc.match_id END) as wins,
    COUNT(DISTINCT CASE WHEN m.home_score = m.away_score THEN mc.match_id END) as draws,
    COUNT(DISTINCT CASE
        WHEN (mc.team_id = m.home_team_id AND m.home_score < m.away_score)
          OR (mc.team_id = m.away_team_id AND m.away_score < m.home_score)
        THEN mc.match_id END) as losses,
    MIN(m.match_date) as first_match,
    MAX(m.match_date) as last_match
FROM coaches c
LEFT JOIN match_coaches mc ON c.coach_id = mc.coach_id
LEFT JOIN matches m ON mc.match_id = m.match_id
GROUP BY c.coach_id, c.name, c.normalized_name, c.birth_date;

CREATE UNIQUE INDEX idx_mv_coach_record_coach_id ON mv_coach_record(coach_id);
CREATE INDEX idx_mv_coach_record_name ON mv_coach_record(normalized_name);

-- ============================================================
-- ADDITIONAL PERFORMANCE INDEXES
-- ============================================================

-- Composite indexes for common join patterns
CREATE INDEX IF NOT EXISTS idx_match_lineups_match_player ON match_lineups(match_id, player_id);
CREATE INDEX IF NOT EXISTS idx_goals_match_player ON goals(match_id, player_id);
CREATE INDEX IF NOT EXISTS idx_cards_match_player ON cards(match_id, player_id);

-- Date range queries
CREATE INDEX IF NOT EXISTS idx_matches_date_range ON matches(match_date) WHERE match_date IS NOT NULL;

-- Competition lookups
CREATE INDEX IF NOT EXISTS idx_season_comp_lookup ON season_competitions(season_id, competition_id);

-- ============================================================
-- REFRESH FUNCTION
-- ============================================================
CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_career_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_team_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_season_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_coach_record;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- VERIFICATION
-- ============================================================
SELECT 'Materialized views created successfully' as status;

-- Quick stats
SELECT
    'mv_player_career_stats' as view_name,
    COUNT(*) as rows
FROM mv_player_career_stats
UNION ALL
SELECT 'mv_team_stats', COUNT(*) FROM mv_team_stats
UNION ALL
SELECT 'mv_season_summary', COUNT(*) FROM mv_season_summary
UNION ALL
SELECT 'mv_coach_record', COUNT(*) FROM mv_coach_record;
