// Quiz API types

export interface QuizGameCreateRequest {
  topic?: string;
  difficulty: 'easy' | 'medium' | 'hard';
  num_rounds: number;
  game_mode?: 'classic' | 'speed' | 'survival';
  category_id?: string;
  player_names: string[];
}

export interface QuizGameResponse {
  game_id: string;
  topic?: string;
  difficulty: 'easy' | 'medium' | 'hard';
  num_rounds: number;
  current_round: number;
  status: 'pending' | 'in_progress' | 'completed' | 'abandoned';
  game_mode: 'classic' | 'speed' | 'survival';
  category?: {
    category_id: string;
    name: string;
    display_name_de: string;
  };
  players: string[];
  created_at: string;
  updated_at: string;
  generation_job_id?: string;
  generation_status?: 'queued' | 'running' | 'succeeded' | 'failed';
}

export interface QuizQuestionResponse {
  question_id: string;
  question_text: string;
  alternatives: string[];
  difficulty: 'easy' | 'medium' | 'hard';
  category?: string;
  hint?: string;
  time_limit_seconds: number;
}

export interface QuizAnswerRequest {
  player_name: string;
  answer: string;
  time_taken: number; // seconds
}

export interface QuizAnswerResponse {
  correct: boolean;
  correct_answer: string;
  explanation?: string;
  points_earned: number;
}

export interface QuizLeaderboardResponse {
  game_id: string;
  leaderboard: Array<{
    player_name: string;
    score: number;
    correct_answers: number;
    total_questions: number;
    average_time: number;
  }>;
}

// AI Service types
export interface QuestionGeneratorInput {
  category: string;
  difficulty: 'easy' | 'medium' | 'hard';
  previousQuestions: string[];
  count: number;
  schemaContext: string;
  rounds: number;
  numberOfPlayers: number;
  knowledgeBase?: string;
}

export interface GeneratedQuestion {
  questionText: string;
  correct_answer: string;
  category?: string;
  difficulty?: 'easy' | 'medium' | 'hard';
}

export interface QuestionGeneratorOutput {
  rejected: boolean;
  rejection_reason?: string;
  questions: GeneratedQuestion[];
}

export interface AnswerGeneratorInput {
  question: string;
  correctAnswer: string;
  difficulty: 'easy' | 'medium' | 'hard';
  category?: string;
  knowledgeBaseContext?: string;
}

export interface AnswerGeneratorOutput {
  correctAnswer: string;
  incorrectAnswers: string[];
  explanation: string;
  evidenceScore: number;
}

// Knowledge Base Generator types (for quiz question generation pipeline)
export interface KnowledgeBaseInput {
  thema: string;
  schwierigkeitsgrad: 'easy' | 'medium' | 'hard';
  anzahlAbfragen: number;
  schemaContext: string;
}

export interface KnowledgeBaseQuery {
  sql_query: string;
  reason: string;
}

export interface KnowledgeBaseOutput {
  thema: string;
  schwierigkeitsgrad: string;
  rejection_reason?: string | null;
  queries: KnowledgeBaseQuery[];
}

export interface KnowledgeBaseResult {
  sql_query: string;
  reason: string;
  result: any[];
}

// Quiz Generation Progress types
export interface QuizGenerationProgress {
  game_id: string;
  total_rounds: number;
  completed_rounds: number;
  current_round?: number;
  current_status?: 'pending' | 'generating_alternatives' | 'round_created' | 'failed';
  error_message?: string;
  rounds: Array<{
    round_number: number;
    status: 'pending' | 'generating_alternatives' | 'round_created' | 'failed';
    question_preview?: string;
    error_message?: string;
  }>;
}

export interface QuizGenerationProgressResponse {
  game_id: string;
  status: 'generating' | 'completed' | 'failed';
  progress: QuizGenerationProgress;
}
