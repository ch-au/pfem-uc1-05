// Database types matching the existing PostgreSQL schema

export interface ChatSession {
  session_id: string;
  created_at: Date;
  updated_at: Date;
  expires_at: Date;
  metadata?: Record<string, any>;
}

export interface ChatMessage {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata?: {
    sql_query?: string;
    sql_execution_time_ms?: number;
    sql_result_count?: number;
    confidence_score?: number;
    visualization_type?: 'table' | 'chart' | 'stat' | 'timeline';
  };
  langfuse_trace_id?: string;
  created_at: Date;
}

export interface QuizGame {
  game_id: string;
  topic?: string;
  difficulty: 'easy' | 'medium' | 'hard';
  num_rounds: number;
  current_round: number;
  status: 'pending' | 'in_progress' | 'completed' | 'abandoned';
  game_mode?: 'classic' | 'speed' | 'survival';
  category_id?: string;
  created_at: Date;
  updated_at: Date;
  completed_at?: Date;
}

export interface QuizQuestion {
  question_id: string;
  question_text: string;
  correct_answer: string;
  alternatives: string[]; // JSON array
  explanation?: string;
  difficulty: 'easy' | 'medium' | 'hard';
  topic?: string;
  category_id?: string;
  evidence_score?: number;
  sql_query?: string;
  metadata?: Record<string, any>;
  answer_type?: 'number' | 'string' | 'date' | 'list';
  langfuse_trace_id?: string;
  langfuse_observation_id?: string;
  times_used: number;
  times_correct: number;
  average_time_seconds?: number;
  created_at: Date;
  created_by: string;
}

export interface QuizRound {
  round_id: string;
  game_id: string;
  question_id: string;
  round_number: number;
  started_at: Date;
}

export interface QuizAnswer {
  answer_id: string;
  round_id: string;
  player_name: string;
  quiz_player_id?: string;
  answer: string;
  is_correct: boolean;
  time_taken: number; // seconds
  points_earned: number;
  submitted_at: Date;
}

export interface QuizPlayer {
  player_id: string;
  player_name: string;
  total_games: number;
  total_correct: number;
  total_questions: number;
  average_time_seconds?: number;
  best_streak: number;
  created_at: Date;
  updated_at: Date;
}

export interface QuizCategory {
  category_id: string;
  name: string;
  display_name_de: string;
  description?: string;
  icon_name?: string;
  created_at: Date;
}
