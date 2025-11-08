// Chat API types

export interface ChatMessageRequest {
  session_id: string;
  content: string;
}

export interface ChatMessageResponse {
  message_id: string;
  role: 'assistant';
  content: string;
  metadata?: {
    sql_query?: string;
    sql_execution_time_ms?: number;
    sql_result_count?: number;
    confidence_score?: number;
    visualization_type?: 'table' | 'chart' | 'stat' | 'timeline';
    highlights?: string[];
    follow_up_questions?: string[];
  };
  langfuse_trace_id?: string;
  created_at: string;
}

export interface ChatSessionResponse {
  session_id: string;
  created_at: string;
  expires_at: string;
}

export interface ChatHistoryResponse {
  session_id: string;
  messages: Array<{
    message_id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    metadata?: Record<string, any>;
    created_at: string;
  }>;
}

// AI Service types
export interface SQLGeneratorInput {
  userQuestion: string;
  conversationHistory: Array<{ role: string; content: string }>;
  schemaContext: string;
}

export interface SQLGeneratorOutput {
  sql: string;
  confidence: number;
  reasoning: string;
  needsClarification?: string;
}

export interface AnswerFormatterInput {
  userQuestion: string;
  sqlQuery: string;
  sqlResult: any[];
  resultMetadata: {
    rowCount: number;
    executionTimeMs: number;
  };
}

export interface AnswerFormatterOutput {
  answer: string;
  highlights: string[];
  suggestedVisualization?: 'table' | 'chart' | 'stat' | 'timeline';
  followUpQuestions?: string[];
}
