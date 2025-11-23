/**
 * TypeScript interfaces for API models
 * Matching backend models from models.py
 */

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export interface ChatResponse {
  message_id: string;
  role: 'assistant';
  content: string;
  metadata?: {
    sql_query?: string;
    sql_execution_time_ms?: number;
    sql_result_count?: number;
    confidence_score?: number;
    visualization_type?: string;
    highlights?: string[];
    follow_up_questions?: string[];
  };
  langfuse_trace_id?: string;
  created_at: string;
}

export interface ChatSessionRequest {
  metadata?: Record<string, unknown>;
}

export interface ChatSessionResponse {
  session_id: string;
}

export interface ChatHistoryResponse {
  session_id: string;
  messages: ChatMessage[];
}

export interface QuizQuestion {
  question_text: string;
  correct_answer: string;
  alternatives: string[];
  explanation?: string;
  difficulty: 'easy' | 'medium' | 'hard';
  topic?: string;
  evidence_score?: number;
  sql_query?: string;
  metadata?: Record<string, unknown>;
  round_id?: string;
  round_number?: number;
}

export interface QuizGameCreate {
  topic?: string | null;
  difficulty: 'easy' | 'medium' | 'hard';
  num_rounds: number;
  player_names: string[];
}

export interface QuizAnswer {
  player_name: string;
  answer: string;
  time_taken: number;
}

export interface QuizAnswerRequest {
  round_id: string;
  answer: QuizAnswer;
}

export interface QuizAnswerResponse {
  correct: boolean;
  correct_answer: string;
  points_earned: number;
  explanation?: string;
}

export interface QuizGameState {
  game_id: string;
  status: 'pending' | 'in_progress' | 'completed';
  topic?: string;
  difficulty: string;
  num_rounds: number;
  current_round: number;
  players: string[];
  created_at: string;
}

export interface QuizLeaderboardEntry {
  player_name: string;
  score: number;
  correct_answers: number;
  total_questions: number;
  average_time: number;
}

export interface QuizLeaderboardResponse {
  game_id: string;
  leaderboard: QuizLeaderboardEntry[];
}

export interface QuizNextRoundResponse {
  status: 'in_progress' | 'completed';
  current_round?: number;
}

export interface QuizGenerationProgressResponse {
  game_id: string;
  status: 'generating' | 'completed' | 'failed';
  progress: {
    game_id: string;
    total_rounds: number;
    completed_rounds: number;
    current_round?: number;
    current_status?: string;
    error_message?: string;
    rounds: Array<{
      round_number: number;
      status: string;
      question_preview?: string;
      error_message?: string;
    }>;
  };
}

export interface ApiError {
  detail: string;
}

