import axios from 'axios';
import type {
  ChatMessage,
  ChatResponse,
  ChatSessionResponse,
  ChatHistoryResponse,
} from '../types/api';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export const chatService = {
  /**
   * Create a new chat session
   */
  async createSession(metadata: Record<string, unknown> = {}): Promise<string> {
    const response = await api.post<ChatSessionResponse>('/chat/session', {
      metadata,
    });
    return response.data.session_id;
  },

  /**
   * Send a message and get a response
   */
  async sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
    const response = await api.post<ChatResponse>('/chat/message', {
      session_id: sessionId,
      content: message,
    });
    return response.data;
  },

  /**
   * Get chat history for a session
   */
  async getHistory(sessionId: string): Promise<ChatMessage[]> {
    const response = await api.get<ChatHistoryResponse>(`/chat/session/${sessionId}`);
    return response.data.messages;
  },
};



