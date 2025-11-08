import { postgresService } from '../database/postgres.service.js';
import { promptsService } from '../ai/prompts.service.js';
import { getSchemaContext } from '../../config/schema-context.js';
import type {
  ChatSession,
  ChatMessage,
  ChatMessageRequest,
  ChatMessageResponse,
} from '@fsv/shared-types';

export class ChatService {
  /**
   * Create a new chat session
   */
  async createSession(): Promise<ChatSession> {
    const result = await postgresService.queryOne<ChatSession>(
      `INSERT INTO public.chat_sessions (expires_at)
       VALUES (CURRENT_TIMESTAMP + INTERVAL '1 hour')
       RETURNING *`
    );

    if (!result) {
      throw new Error('Failed to create chat session');
    }

    return result;
  }

  /**
   * Get chat session by ID
   */
  async getSession(sessionId: string): Promise<ChatSession | null> {
    return await postgresService.queryOne<ChatSession>(
      `SELECT * FROM public.chat_sessions WHERE session_id = $1`,
      [sessionId]
    );
  }

  /**
   * Get chat history
   */
  async getHistory(sessionId: string): Promise<ChatMessage[]> {
    return await postgresService.queryMany<ChatMessage>(
      `SELECT * FROM public.chat_messages
       WHERE session_id = $1
       ORDER BY created_at ASC`,
      [sessionId]
    );
  }

  /**
   * Process a chat message (main flow)
   */
  async processMessage(request: ChatMessageRequest): Promise<ChatMessageResponse> {
    const { session_id, content } = request;

    // 1. Verify session exists
    const session = await this.getSession(session_id);
    if (!session) {
      throw new Error('Session not found');
    }

    // 2. Save user message
    await this.saveMessage({
      session_id,
      role: 'user',
      content,
    });

    // 3. Get conversation history (last 3 messages for context)
    const history = await this.getHistory(session_id);
    const conversationHistory = history.slice(-6).map((msg) => ({
      role: msg.role,
      content: msg.content,
    }));

    try {
      // 4. PROMPT 1: Generate SQL from question
      const sqlGeneration = await promptsService.executeChatSQLGenerator({
        userQuestion: content,
        conversationHistory,
        schemaContext: getSchemaContext(),
      });

      const { sql, confidence, needsClarification } = sqlGeneration.result;

      // Check if clarification is needed
      if (needsClarification || !sql) {
        const clarificationMessage = await this.saveMessage({
          session_id,
          role: 'assistant',
          content: needsClarification || 'Ich bin mir nicht sicher, was du meinst. Kannst du die Frage präzisieren?',
          metadata: {
            confidence_score: confidence,
            langfuse_trace_id: sqlGeneration.traceId,
          },
        });

        return {
          message_id: clarificationMessage.message_id,
          role: 'assistant',
          content: clarificationMessage.content,
          metadata: {
            confidence_score: confidence,
          },
          langfuse_trace_id: sqlGeneration.traceId,
          created_at: clarificationMessage.created_at.toISOString(),
        };
      }

      // 5. Execute SQL query
      const { rows, executionTimeMs } = await postgresService.executeUserQuery(sql);

      // 6. PROMPT 2: Format answer
      const answerFormatting = await promptsService.executeChatAnswerFormatter({
        userQuestion: content,
        sqlQuery: sql,
        sqlResult: rows,
        resultMetadata: {
          rowCount: rows.length,
          executionTimeMs,
        },
      });

      const {
        answer,
        highlights,
        suggestedVisualization,
        followUpQuestions,
      } = answerFormatting.result;

      // 7. Save assistant message
      const assistantMessage = await this.saveMessage({
        session_id,
        role: 'assistant',
        content: answer,
        metadata: {
          sql_query: sql,
          sql_execution_time_ms: executionTimeMs,
          sql_result_count: rows.length,
          confidence_score: confidence,
          visualization_type: suggestedVisualization ?? null,
          langfuse_trace_id: answerFormatting.traceId,
        },
      });

      // 8. Return formatted response
      return {
        message_id: assistantMessage.message_id,
        role: 'assistant',
        content: answer,
        metadata: {
          sql_query: sql,
          sql_execution_time_ms: executionTimeMs,
          sql_result_count: rows.length,
          confidence_score: confidence,
          visualization_type: suggestedVisualization,
          highlights,
          follow_up_questions: followUpQuestions,
        },
        langfuse_trace_id: answerFormatting.traceId,
        created_at: assistantMessage.created_at.toISOString(),
      };
    } catch (error: any) {
      // Handle errors gracefully
      console.error('Error processing chat message:', error);

      const errorMessage = await this.saveMessage({
        session_id,
        role: 'assistant',
        content: 'Entschuldigung, es gab einen Fehler bei der Verarbeitung deiner Anfrage. Bitte versuche es erneut oder formuliere die Frage anders.',
      });

      return {
        message_id: errorMessage.message_id,
        role: 'assistant',
        content: errorMessage.content,
        created_at: errorMessage.created_at.toISOString(),
      };
    }
  }

  /**
   * Save a message to the database
   */
  private async saveMessage(data: {
    session_id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    metadata?: any;
  }): Promise<ChatMessage> {
    const result = await postgresService.queryOne<ChatMessage>(
      `INSERT INTO public.chat_messages (session_id, role, content, metadata,
        sql_query, sql_execution_time_ms, sql_result_count, confidence_score,
        visualization_type, langfuse_trace_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       RETURNING *`,
      [
        data.session_id,
        data.role,
        data.content,
        data.metadata ? JSON.stringify(data.metadata) : null,
        data.metadata?.sql_query ?? null,
        data.metadata?.sql_execution_time_ms ?? null,
        data.metadata?.sql_result_count ?? null,
        data.metadata?.confidence_score ?? null,
        data.metadata?.visualization_type ?? null,
        data.metadata?.langfuse_trace_id ?? null,
      ]
    );

    if (!result) {
      throw new Error('Failed to save message');
    }

    return result;
  }

  /**
   * Delete a session and all its messages
   */
  async deleteSession(sessionId: string): Promise<void> {
    await postgresService.query(
      `DELETE FROM public.chat_sessions WHERE session_id = $1`,
      [sessionId]
    );
  }
}

// Singleton instance
export const chatService = new ChatService();
