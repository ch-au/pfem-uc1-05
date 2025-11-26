-- FSV Mainz 05 Archive - PostgreSQL Schema
-- Creates all tables matching SQLite schema with PostgreSQL-specific optimizations

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop existing tables in correct order (if recreating)
DROP TABLE IF EXISTS season_matchdays CASCADE;
DROP TABLE IF EXISTS match_notes CASCADE;
DROP TABLE IF EXISTS cards CASCADE;
DROP TABLE IF EXISTS goals CASCADE;
DROP TABLE IF EXISTS match_substitutions CASCADE;
DROP TABLE IF EXISTS match_lineups CASCADE;
DROP TABLE IF EXISTS match_referees CASCADE;
DROP TABLE IF EXISTS match_coaches CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS season_squads CASCADE;
DROP TABLE IF EXISTS coach_careers CASCADE;
DROP TABLE IF EXISTS player_careers CASCADE;
DROP TABLE IF EXISTS player_aliases CASCADE;
DROP TABLE IF EXISTS season_competitions CASCADE;
DROP TABLE IF EXISTS seasons CASCADE;
DROP TABLE IF EXISTS competitions CASCADE;
DROP TABLE IF EXISTS referees CASCADE;
DROP TABLE IF EXISTS coaches CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS teams CASCADE;

-- Teams
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    team_type TEXT,
    profile_url TEXT,
    name_embedding vector(1024)  -- For semantic search
);

CREATE INDEX idx_teams_normalized_name ON teams(normalized_name);

-- Competitions
CREATE TABLE competitions (
    competition_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    level TEXT,
    gender TEXT
);

CREATE INDEX idx_competitions_normalized_name ON competitions(normalized_name);

-- Seasons
CREATE TABLE seasons (
    season_id SERIAL PRIMARY KEY,
    label TEXT UNIQUE NOT NULL,
    start_year INTEGER,
    end_year INTEGER,
    team_id INTEGER REFERENCES teams(team_id)
);

CREATE INDEX idx_seasons_years ON seasons(start_year, end_year);

-- Season Competitions (junction)
CREATE TABLE season_competitions (
    season_competition_id SERIAL PRIMARY KEY,
    season_id INTEGER REFERENCES seasons(season_id),
    competition_id INTEGER REFERENCES competitions(competition_id),
    stage_label TEXT,
    source_path TEXT,
    UNIQUE (season_id, competition_id)
);

-- Referees
CREATE TABLE referees (
    referee_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    profile_url TEXT
);

CREATE INDEX idx_referees_normalized_name ON referees(normalized_name);

-- Coaches
CREATE TABLE coaches (
    coach_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    birth_date TEXT,
    birth_place TEXT,
    nationality TEXT,
    profile_url TEXT,
    name_embedding vector(1024)
);

CREATE INDEX idx_coaches_normalized_name ON coaches(normalized_name);

-- Players
CREATE TABLE players (
    player_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    birth_date TEXT,
    birth_place TEXT,
    height_cm INTEGER,
    weight_kg INTEGER,
    primary_position TEXT,
    nationality TEXT,
    profile_url TEXT,
    image_url TEXT,
    name_embedding vector(1024)
);

CREATE INDEX idx_players_normalized_name ON players(normalized_name);
CREATE INDEX idx_players_name_trgm ON players USING gin(name gin_trgm_ops);

-- Player Aliases
CREATE TABLE player_aliases (
    alias_id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    UNIQUE (player_id, normalized_alias)
);

-- Player Careers
CREATE TABLE player_careers (
    career_id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    team_name TEXT,
    start_year INTEGER,
    end_year INTEGER,
    notes TEXT
);

CREATE INDEX idx_player_careers_player ON player_careers(player_id);

-- Coach Careers
CREATE TABLE coach_careers (
    career_id SERIAL PRIMARY KEY,
    coach_id INTEGER REFERENCES coaches(coach_id),
    team_name TEXT,
    start_date TEXT,
    end_date TEXT,
    role TEXT
);

CREATE INDEX idx_coach_careers_coach ON coach_careers(coach_id);

-- Season Squads
CREATE TABLE season_squads (
    season_squad_id SERIAL PRIMARY KEY,
    season_competition_id INTEGER REFERENCES season_competitions(season_competition_id),
    player_id INTEGER REFERENCES players(player_id),
    position_group TEXT,
    shirt_number INTEGER,
    status TEXT,
    notes TEXT,
    UNIQUE (season_competition_id, player_id, position_group)
);

-- Matches
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    season_competition_id INTEGER REFERENCES season_competitions(season_competition_id),
    round_name TEXT,
    matchday INTEGER,
    leg INTEGER,
    match_date TEXT,
    kickoff_time TEXT,
    venue TEXT,
    attendance INTEGER,
    referee_id INTEGER REFERENCES referees(referee_id),
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    halftime_home INTEGER,
    halftime_away INTEGER,
    extra_time_home INTEGER,
    extra_time_away INTEGER,
    penalties_home INTEGER,
    penalties_away INTEGER,
    source_file TEXT,
    UNIQUE (season_competition_id, source_file)
);

CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_matches_teams ON matches(home_team_id, away_team_id);
CREATE INDEX idx_matches_season_comp ON matches(season_competition_id);

-- Match Coaches
CREATE TABLE match_coaches (
    match_coach_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id),
    team_id INTEGER REFERENCES teams(team_id),
    coach_id INTEGER REFERENCES coaches(coach_id),
    role TEXT
);

CREATE INDEX idx_match_coaches_match ON match_coaches(match_id);
CREATE INDEX idx_match_coaches_coach ON match_coaches(coach_id);

-- Match Referees
CREATE TABLE match_referees (
    match_referee_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id),
    referee_id INTEGER REFERENCES referees(referee_id),
    role TEXT
);

-- Match Lineups
CREATE TABLE match_lineups (
    lineup_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id),
    team_id INTEGER REFERENCES teams(team_id),
    player_id INTEGER REFERENCES players(player_id),
    shirt_number INTEGER,
    is_starter INTEGER,
    minute_on INTEGER,
    stoppage_on INTEGER,
    minute_off INTEGER,
    stoppage_off INTEGER
);

CREATE INDEX idx_match_lineups_match ON match_lineups(match_id);
CREATE INDEX idx_match_lineups_player ON match_lineups(player_id);

-- Match Substitutions
CREATE TABLE match_substitutions (
    substitution_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id),
    team_id INTEGER REFERENCES teams(team_id),
    minute INTEGER,
    stoppage INTEGER,
    player_on_id INTEGER REFERENCES players(player_id),
    player_off_id INTEGER REFERENCES players(player_id)
);

CREATE INDEX idx_match_subs_match ON match_substitutions(match_id);

-- Goals
CREATE TABLE goals (
    goal_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id),
    team_id INTEGER REFERENCES teams(team_id),
    player_id INTEGER REFERENCES players(player_id),
    assist_player_id INTEGER REFERENCES players(player_id),
    minute INTEGER,
    stoppage INTEGER,
    score_home INTEGER,
    score_away INTEGER,
    event_type TEXT
);

CREATE INDEX idx_goals_match ON goals(match_id);
CREATE INDEX idx_goals_player ON goals(player_id);

-- Cards
CREATE TABLE cards (
    card_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id),
    team_id INTEGER REFERENCES teams(team_id),
    player_id INTEGER REFERENCES players(player_id),
    minute INTEGER,
    stoppage INTEGER,
    card_type TEXT
);

CREATE INDEX idx_cards_match ON cards(match_id);
CREATE INDEX idx_cards_player ON cards(player_id);

-- Match Notes
CREATE TABLE match_notes (
    note_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id),
    note TEXT,
    note_type TEXT
);

-- Season Matchdays (standings progression)
CREATE TABLE season_matchdays (
    season_matchday_id SERIAL PRIMARY KEY,
    season_competition_id INTEGER REFERENCES season_competitions(season_competition_id),
    matchday INTEGER,
    date TEXT,
    position INTEGER,
    points INTEGER,
    goals_for INTEGER,
    goals_against INTEGER,
    goal_difference INTEGER
);

-- Enable trigram extension for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Add trigram indexes for fuzzy name search
CREATE INDEX IF NOT EXISTS idx_players_name_trgm ON players USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_teams_name_trgm ON teams USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_coaches_name_trgm ON coaches USING gin(name gin_trgm_ops);

-- ============================================================
-- CHAT SYSTEM TABLES
-- ============================================================

-- Chat Sessions Table
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour'),
    metadata JSONB
);

-- Chat Messages Table
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    langfuse_trace_id TEXT,
    sql_query TEXT,
    sql_execution_time_ms INTEGER,
    sql_result_count INTEGER,
    confidence_score NUMERIC(5, 2),
    visualization_type TEXT
);

-- Chat indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_expires_at ON chat_sessions(expires_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for auto-updating updated_at
DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Summary
SELECT 'Schema created successfully' as status;
