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
  created_at: string;
  updated_at: string;
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
  is_correct: boolean;
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
}

export interface QuestionGeneratorOutput {
  questions: Array<{
    questionText: string;
    category: string;
    difficulty: 'easy' | 'medium' | 'hard';
    sqlQueryNeeded: string;
    expectedAnswerType: 'number' | 'string' | 'date' | 'list';
    hint?: string;
  }>;
}

export interface AnswerGeneratorInput {
  question: string;
  sqlQuery: string;
  sqlResult: any[];
  difficulty: 'easy' | 'medium' | 'hard';
}

export interface AnswerGeneratorOutput {
  correctAnswer: string;
  incorrectAnswers: string[];
  explanation: string;
  evidenceScore: number;
}

// Quiz Generation Progress types
export interface QuizGenerationProgress {
  game_id: string;
  total_rounds: number;
  completed_rounds: number;
  current_round?: number;
  current_status?: 'pending' | 'sql_generated' | 'answer_verified' | 'round_created' | 'failed';
  error_message?: string;
  rounds: Array<{
    round_number: number;
    status: 'pending' | 'sql_generated' | 'answer_verified' | 'round_created' | 'failed';
    question_preview?: string;
    error_message?: string;
  }>;
}

export interface QuizGenerationProgressResponse {
  game_id: string;
  status: 'generating' | 'completed' | 'failed';
  progress: QuizGenerationProgress;
}
