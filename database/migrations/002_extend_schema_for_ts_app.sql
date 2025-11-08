-- Migration: Extend existing schema for TypeScript app
-- This migration ONLY ADDS new columns and tables
-- It does NOT modify or delete existing structures

-- ========================================
-- 1. ADD Quiz Categories Table
-- ========================================
CREATE TABLE IF NOT EXISTS public.quiz_categories (
    category_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    display_name_de TEXT NOT NULL,
    description TEXT,
    icon_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default categories
INSERT INTO public.quiz_categories (name, display_name_de, description, icon_name) VALUES
    ('top_scorers', 'Torschützen', 'Fragen zu den besten Torjägern des Vereins', 'target'),
    ('historic_matches', 'Historische Spiele', 'Legendäre Spiele und unvergessliche Momente', 'calendar'),
    ('players', 'Spieler & Legenden', 'Fragen zu Spielern und Vereinslegenden', 'users'),
    ('seasons', 'Saisonen & Erfolge', 'Fragen zu Spielzeiten und sportlichen Erfolgen', 'trophy'),
    ('opponents', 'Gegner & Derbys', 'Fragen zu Gegnern und Rivalitäten', 'shield'),
    ('statistics', 'Statistiken & Rekorde', 'Zahlen, Daten, Fakten rund um Mainz 05', 'bar-chart')
ON CONFLICT (name) DO NOTHING;

-- ========================================
-- 2. ADD Quiz Players Table (Player Stats)
-- ========================================
CREATE TABLE IF NOT EXISTS public.quiz_players (
    player_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_name TEXT NOT NULL UNIQUE,
    total_games INTEGER DEFAULT 0,
    total_correct INTEGER DEFAULT 0,
    total_questions INTEGER DEFAULT 0,
    average_time_seconds NUMERIC(10, 2),
    best_streak INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 3. EXTEND quiz_questions table
-- ========================================
ALTER TABLE public.quiz_questions
    ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES public.quiz_categories(category_id),
    ADD COLUMN IF NOT EXISTS langfuse_trace_id TEXT,
    ADD COLUMN IF NOT EXISTS langfuse_observation_id TEXT,
    ADD COLUMN IF NOT EXISTS answer_type TEXT CHECK (answer_type IN ('number', 'string', 'date', 'list')),
    ADD COLUMN IF NOT EXISTS times_used INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS times_correct INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS average_time_seconds NUMERIC(10, 2);

-- ========================================
-- 4. EXTEND quiz_games table
-- ========================================
ALTER TABLE public.quiz_games
    ADD COLUMN IF NOT EXISTS game_mode TEXT DEFAULT 'classic' CHECK (
        game_mode IN ('classic', 'speed', 'survival')
    ),
    ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES public.quiz_categories(category_id);

-- ========================================
-- 5. EXTEND quiz_answers table
-- ========================================
ALTER TABLE public.quiz_answers
    ADD COLUMN IF NOT EXISTS quiz_player_id UUID REFERENCES public.quiz_players(player_id);

-- ========================================
-- 6. EXTEND chat_messages table
-- ========================================
ALTER TABLE public.chat_messages
    ADD COLUMN IF NOT EXISTS langfuse_trace_id TEXT,
    ADD COLUMN IF NOT EXISTS sql_query TEXT,
    ADD COLUMN IF NOT EXISTS sql_execution_time_ms INTEGER,
    ADD COLUMN IF NOT EXISTS sql_result_count INTEGER,
    ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(3, 2),
    ADD COLUMN IF NOT EXISTS visualization_type TEXT CHECK (
        visualization_type IN ('table', 'chart', 'stat', 'timeline', NULL)
    );

-- ========================================
-- 7. CREATE Indices for Performance
-- ========================================
CREATE INDEX IF NOT EXISTS idx_quiz_questions_category ON public.quiz_questions(category_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_langfuse ON public.quiz_questions(langfuse_trace_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_times_used ON public.quiz_questions(times_used DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_answer_type ON public.quiz_questions(answer_type);

CREATE INDEX IF NOT EXISTS idx_quiz_games_category ON public.quiz_games(category_id);
CREATE INDEX IF NOT EXISTS idx_quiz_games_mode ON public.quiz_games(game_mode);

CREATE INDEX IF NOT EXISTS idx_quiz_players_name ON public.quiz_players(player_name);
CREATE INDEX IF NOT EXISTS idx_quiz_players_total_games ON public.quiz_players(total_games DESC);

CREATE INDEX IF NOT EXISTS idx_quiz_answers_player ON public.quiz_answers(quiz_player_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_langfuse ON public.chat_messages(langfuse_trace_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_visualization ON public.chat_messages(visualization_type);

-- ========================================
-- 8. CREATE Trigger for Quiz Player Stats
-- ========================================
CREATE OR REPLACE FUNCTION update_quiz_player_stats()
RETURNS TRIGGER AS $$
DECLARE
    v_streak INTEGER;
BEGIN
    -- Update basic stats
    UPDATE public.quiz_players
    SET
        total_questions = total_questions + 1,
        total_correct = total_correct + (CASE WHEN NEW.is_correct THEN 1 ELSE 0 END),
        average_time_seconds = (
            SELECT AVG(time_taken)
            FROM public.quiz_answers
            WHERE quiz_player_id = NEW.quiz_player_id
        ),
        updated_at = CURRENT_TIMESTAMP
    WHERE player_id = NEW.quiz_player_id;

    -- Calculate and update streak
    IF NEW.is_correct THEN
        -- Get current streak
        SELECT
            COUNT(*)
        INTO v_streak
        FROM (
            SELECT is_correct,
                   SUM(CASE WHEN NOT is_correct THEN 1 ELSE 0 END)
                       OVER (ORDER BY submitted_at DESC) as grp
            FROM public.quiz_answers
            WHERE quiz_player_id = NEW.quiz_player_id
            ORDER BY submitted_at DESC
        ) sub
        WHERE grp = 0 AND is_correct = true;

        -- Update streak
        UPDATE public.quiz_players
        SET
            current_streak = v_streak,
            best_streak = GREATEST(best_streak, v_streak)
        WHERE player_id = NEW.quiz_player_id;
    ELSE
        -- Reset current streak on wrong answer
        UPDATE public.quiz_players
        SET current_streak = 0
        WHERE player_id = NEW.quiz_player_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if exists
DROP TRIGGER IF EXISTS update_player_stats_on_answer ON public.quiz_answers;

-- Create trigger
CREATE TRIGGER update_player_stats_on_answer
    AFTER INSERT ON public.quiz_answers
    FOR EACH ROW
    WHEN (NEW.quiz_player_id IS NOT NULL)
    EXECUTE FUNCTION update_quiz_player_stats();

-- ========================================
-- 9. CREATE Trigger for Question Stats
-- ========================================
CREATE OR REPLACE FUNCTION update_question_stats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.quiz_questions
    SET
        times_used = times_used + 1,
        times_correct = times_correct + (CASE WHEN NEW.is_correct THEN 1 ELSE 0 END),
        average_time_seconds = (
            SELECT AVG(time_taken)
            FROM public.quiz_answers qa
            JOIN public.quiz_rounds qr ON qa.round_id = qr.round_id
            WHERE qr.question_id = (
                SELECT question_id
                FROM public.quiz_rounds
                WHERE round_id = NEW.round_id
            )
        )
    WHERE question_id = (
        SELECT question_id
        FROM public.quiz_rounds
        WHERE round_id = NEW.round_id
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if exists
DROP TRIGGER IF EXISTS update_question_stats_on_answer ON public.quiz_answers;

-- Create trigger
CREATE TRIGGER update_question_stats_on_answer
    AFTER INSERT ON public.quiz_answers
    FOR EACH ROW
    EXECUTE FUNCTION update_question_stats();

-- ========================================
-- 10. UPDATE existing triggers to work with new columns
-- ========================================
CREATE TRIGGER update_quiz_players_updated_at
    BEFORE UPDATE ON public.quiz_players
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- 11. CREATE Helper Function: Get or Create Player
-- ========================================
CREATE OR REPLACE FUNCTION get_or_create_quiz_player(p_player_name TEXT)
RETURNS UUID AS $$
DECLARE
    v_player_id UUID;
BEGIN
    -- Try to find existing player
    SELECT player_id INTO v_player_id
    FROM public.quiz_players
    WHERE player_name = p_player_name;

    -- Create if not exists
    IF v_player_id IS NULL THEN
        INSERT INTO public.quiz_players (player_name)
        VALUES (p_player_name)
        RETURNING player_id INTO v_player_id;
    END IF;

    RETURN v_player_id;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- Migration Complete
-- ========================================
-- This migration extends the existing schema without breaking changes
-- All existing data remains intact
-- New features are opt-in via new columns and tables
