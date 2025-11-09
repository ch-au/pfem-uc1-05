-- Migration: Add quiz_generation_jobs table
-- This table tracks the progress of quiz question generation for each game

CREATE TABLE IF NOT EXISTS public.quiz_generation_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID NOT NULL REFERENCES public.quiz_games(game_id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'sql_generated', 'answer_verified', 'round_created', 'failed')
    ),
    generated_question_text TEXT,
    generated_sql TEXT,
    sql_result JSONB,
    correct_answer TEXT,
    incorrect_answers JSONB,
    explanation TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, round_number)
);

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_quiz_generation_jobs_game_id ON public.quiz_generation_jobs(game_id);
CREATE INDEX IF NOT EXISTS idx_quiz_generation_jobs_status ON public.quiz_generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_quiz_generation_jobs_game_round ON public.quiz_generation_jobs(game_id, round_number);

-- Add trigger for updated_at
CREATE TRIGGER update_quiz_generation_jobs_updated_at
    BEFORE UPDATE ON public.quiz_generation_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comment
COMMENT ON TABLE public.quiz_generation_jobs IS 'Tracks the progress of quiz question generation for debugging and monitoring';
