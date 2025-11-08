import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import Fastify, { FastifyInstance } from 'fastify';
import cors from '@fastify/cors';
import { chatRoutes } from '../../routes/chat.routes.js';
import { quizRoutes } from '../../routes/quiz.routes.js';
import { healthRoutes } from '../../routes/health.routes.js';
import { createMockOpenRouterService } from '../mocks/openrouter.mock.js';
import { createMockLangfuseService } from '../mocks/langfuse.mock.js';

// Mock AI services
const mockOpenRouter = createMockOpenRouterService();
const mockLangfuse = createMockLangfuseService();

vi.mock('../../services/ai/openrouter.service.js', () => ({
  openRouterService: mockOpenRouter,
}));

vi.mock('../../services/ai/langfuse.service.js', () => ({
  langfuseService: mockLangfuse,
}));

/**
 * E2E tests for API endpoints
 * Tests the full HTTP request/response cycle
 */
describe('API Endpoints (e2e)', () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    if (!process.env.DB_URL) {
      console.warn('⚠️  DB_URL not set, skipping E2E tests');
      return;
    }

    // Create test server
    app = Fastify({
      logger: false, // Disable logging in tests
    });

    await app.register(cors);
    await app.register(healthRoutes);
    await app.register(chatRoutes, { prefix: '/api' });
    await app.register(quizRoutes, { prefix: '/api' });

    await app.ready();
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  describe('Health endpoints', () => {
    it('GET /health should return ok', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const response = await app.inject({
        method: 'GET',
        url: '/health',
      });

      expect(response.statusCode).toBe(200);
      const json = response.json();
      expect(json.status).toBe('ok');
      expect(json.timestamp).toBeDefined();
    });

    it('GET /health/detailed should return detailed status', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const response = await app.inject({
        method: 'GET',
        url: '/health/detailed',
      });

      expect(response.statusCode).toBe(200);
      const json = response.json();
      expect(json.checks).toBeDefined();
      expect(json.checks.database).toBe(true);
      expect(json.checks.openrouter).toBe(true);
    });
  });

  describe('Chat endpoints', () => {
    let sessionId: string;

    it('POST /api/chat/session should create session', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const response = await app.inject({
        method: 'POST',
        url: '/api/chat/session',
      });

      expect(response.statusCode).toBe(201);
      const json = response.json();
      expect(json.session_id).toBeDefined();
      expect(json.created_at).toBeDefined();

      sessionId = json.session_id;
    });

    it('POST /api/chat/message should process message', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      // Create session first if not exists
      if (!sessionId) {
        const sessionResponse = await app.inject({
          method: 'POST',
          url: '/api/chat/session',
        });
        sessionId = sessionResponse.json().session_id;
      }

      const response = await app.inject({
        method: 'POST',
        url: '/api/chat/message',
        payload: {
          session_id: sessionId,
          content: 'Wer ist Rekordtorschütze?',
        },
      });

      expect(response.statusCode).toBe(200);
      const json = response.json();
      expect(json.message_id).toBeDefined();
      expect(json.role).toBe('assistant');
      expect(json.content).toBeDefined();
      expect(json.metadata).toBeDefined();
    });

    it('GET /api/chat/session/:sessionId should return history', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      if (!sessionId) {
        console.log('⏭️  Skipping test - no session');
        return;
      }

      const response = await app.inject({
        method: 'GET',
        url: `/api/chat/session/${sessionId}`,
      });

      expect(response.statusCode).toBe(200);
      const json = response.json();
      expect(json.session_id).toBe(sessionId);
      expect(json.messages).toBeInstanceOf(Array);
    });

    it('DELETE /api/chat/session/:sessionId should delete session', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      if (!sessionId) {
        console.log('⏭️  Skipping test - no session');
        return;
      }

      const response = await app.inject({
        method: 'DELETE',
        url: `/api/chat/session/${sessionId}`,
      });

      expect(response.statusCode).toBe(204);
    });
  });

  describe('Quiz endpoints', () => {
    let gameId: string;

    it('POST /api/quiz/game should create game', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const response = await app.inject({
        method: 'POST',
        url: '/api/quiz/game',
        payload: {
          difficulty: 'easy',
          num_rounds: 1,
          player_names: ['TestPlayer'],
        },
      });

      expect(response.statusCode).toBe(201);
      const json = response.json();
      expect(json.game_id).toBeDefined();
      expect(json.status).toBe('pending');

      gameId = json.game_id;
    }, 60000);

    it('POST /api/quiz/game/:gameId/start should start game', async () => {
      if (!process.env.DB_URL || !gameId) {
        console.log('⏭️  Skipping test - no DB_URL or gameId');
        return;
      }

      const response = await app.inject({
        method: 'POST',
        url: `/api/quiz/game/${gameId}/start`,
      });

      expect(response.statusCode).toBe(200);
      const json = response.json();
      expect(json.status).toBe('in_progress');
    });

    it('GET /api/quiz/game/:gameId/question should get question', async () => {
      if (!process.env.DB_URL || !gameId) {
        console.log('⏭️  Skipping test - no DB_URL or gameId');
        return;
      }

      const response = await app.inject({
        method: 'GET',
        url: `/api/quiz/game/${gameId}/question`,
      });

      expect(response.statusCode).toBe(200);
      const json = response.json();
      expect(json.question_text).toBeDefined();
      expect(json.alternatives).toBeInstanceOf(Array);
    });

    it('POST /api/quiz/game/:gameId/answer should submit answer', async () => {
      if (!process.env.DB_URL || !gameId) {
        console.log('⏭️  Skipping test - no DB_URL or gameId');
        return;
      }

      const response = await app.inject({
        method: 'POST',
        url: `/api/quiz/game/${gameId}/answer`,
        payload: {
          player_name: 'TestPlayer',
          answer: 'Test Answer',
          time_taken: 5.0,
        },
      });

      expect(response.statusCode).toBe(200);
      const json = response.json();
      expect(json.is_correct).toBeDefined();
      expect(json.correct_answer).toBeDefined();
    });

    it('GET /api/quiz/game/:gameId/leaderboard should get leaderboard', async () => {
      if (!process.env.DB_URL || !gameId) {
        console.log('⏭️  Skipping test - no DB_URL or gameId');
        return;
      }

      const response = await app.inject({
        method: 'GET',
        url: `/api/quiz/game/${gameId}/leaderboard`,
      });

      expect(response.statusCode).toBe(200);
      const json = response.json();
      expect(json.game_id).toBe(gameId);
      expect(json.leaderboard).toBeInstanceOf(Array);
    });
  });

  describe('Error handling', () => {
    it('should handle 404 for unknown routes', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const response = await app.inject({
        method: 'GET',
        url: '/api/nonexistent',
      });

      expect(response.statusCode).toBe(404);
    });

    it('should validate request body', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const response = await app.inject({
        method: 'POST',
        url: '/api/chat/message',
        payload: {
          // Missing required fields
          invalid: 'data',
        },
      });

      expect(response.statusCode).toBe(400);
    });
  });
});
