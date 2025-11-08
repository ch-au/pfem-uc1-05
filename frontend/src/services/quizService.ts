import axios from 'axios';
import type {
  QuizGameCreate,
  QuizGameState,
  QuizQuestion,
  QuizAnswerRequest,
  QuizAnswerResponse,
  QuizLeaderboardResponse,
  QuizNextRoundResponse,
} from '../types/api';

const api = axios.create({
  baseURL: '/',
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

export const quizService = {
  /**
   * Create a new quiz game
   */
  async createGame(gameRequest: QuizGameCreate): Promise<string> {
    const response = await api.post<{ game_id: string; message: string }>('/quiz/game', gameRequest);
    return response.data.game_id;
  },

  /**
   * Start a quiz game
   */
  async startGame(gameId: string): Promise<QuizGameState> {
    const response = await api.post<QuizGameState>(`/quiz/game/${gameId}/start`);
    return response.data;
  },

  /**
   * Get current game state
   */
  async getGameState(gameId: string): Promise<QuizGameState> {
    const response = await api.get<QuizGameState>(`/quiz/game/${gameId}`);
    return response.data;
  },

  /**
   * Get current question
   */
  async getCurrentQuestion(gameId: string): Promise<QuizQuestion> {
    const response = await api.get<QuizQuestion>(`/quiz/game/${gameId}/question`);
    return response.data;
  },

  /**
   * Submit an answer
   */
  async submitAnswer(
    gameId: string,
    roundId: string,
    answer: QuizAnswerRequest['answer']
  ): Promise<QuizAnswerResponse> {
    const response = await api.post<QuizAnswerResponse>(`/quiz/game/${gameId}/answer`, {
      round_id: roundId,
      answer,
    });
    return response.data;
  },

  /**
   * Get leaderboard
   */
  async getLeaderboard(gameId: string): Promise<QuizLeaderboardResponse> {
    const response = await api.get<QuizLeaderboardResponse>(`/quiz/game/${gameId}/leaderboard`);
    return response.data;
  },

  /**
   * Advance to next round
   */
  async nextRound(gameId: string): Promise<QuizNextRoundResponse> {
    const response = await api.post<QuizNextRoundResponse>(`/quiz/game/${gameId}/next`);
    return response.data;
  },
};



