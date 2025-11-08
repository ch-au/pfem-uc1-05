-- Quiz application database schema
-- Tables for quiz games, questions, rounds, and answers

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS public.quiz_games (
    game_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    num_rounds INTEGER NOT NULL CHECK (num_rounds > 0),
    current_round INTEGER DEFAULT 0 CHECK (current_round >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'abandoned')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS public.quiz_questions (
    question_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    alternatives JSONB NOT NULL, -- Array of alternative answers
    explanation TEXT,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    topic TEXT,
    evidence_score NUMERIC(5, 2) CHECK (evidence_score >= 0 AND evidence_score <= 100),
    sql_query TEXT, -- SQL query used to find the answer
    metadata JSONB, -- Additional metadata (source table, season, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'ai' -- Track if manually created or AI-generated
);

CREATE TABLE IF NOT EXISTS public.quiz_rounds (
    round_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID NOT NULL REFERENCES public.quiz_games(game_id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES public.quiz_questions(question_id),
    round_number INTEGER NOT NULL CHECK (round_number > 0),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, round_number)
);

CREATE TABLE IF NOT EXISTS public.quiz_answers (
    answer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    round_id UUID NOT NULL REFERENCES public.quiz_rounds(round_id) ON DELETE CASCADE,
    player_name TEXT NOT NULL,
    answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    time_taken NUMERIC(10, 2) NOT NULL CHECK (time_taken >= 0), -- seconds
    points_earned INTEGER DEFAULT 0 CHECK (points_earned >= 0),
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(round_id, player_name) -- One answer per player per round
);

CREATE TABLE IF NOT EXISTS public.chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour'),
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS public.chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.chat_sessions(session_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB, -- SQL queries, sources, confidence scores
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_quiz_games_status ON public.quiz_games(status);
CREATE INDEX IF NOT EXISTS idx_quiz_games_created_at ON public.quiz_games(created_at);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_difficulty ON public.quiz_questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_topic ON public.quiz_questions(topic);
CREATE INDEX IF NOT EXISTS idx_quiz_rounds_game_id ON public.quiz_rounds(game_id);
CREATE INDEX IF NOT EXISTS idx_quiz_answers_round_id ON public.quiz_answers(round_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON public.chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON public.chat_messages(created_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_quiz_games_updated_at
    BEFORE UPDATE ON public.quiz_games
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON public.chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

