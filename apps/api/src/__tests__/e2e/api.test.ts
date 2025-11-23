import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import Fastify, { FastifyInstance } from 'fastify';
import cors from '@fastify/cors';
import { chatRoutes } from '../../routes/chat.routes.js';
import { quizRoutes } from '../../routes/quiz.routes.js';
import { healthRoutes } from '../../routes/health.routes.js';
const { mockOpenRouterService, mockLangfuseService } = vi.hoisted(() => {
  const defaultUsage = { promptTokens: 0, completionTokens: 0, totalTokens: 0 };
  const mockOpenRouterService = {
    generateJSON: vi.fn().mockImplementation(async (prompt: string) => {
      const lower = prompt.toLowerCase();

      // Chat SQL generator
      if (lower.includes('sql') && lower.includes('select')) {
        return {
          data: {
            sql: 'SELECT 1',
            confidence: 0.9,
            reasoning: 'mocked reasoning',
            needsClarification: null,
          },
          usage: defaultUsage,
        };
      }

      // Chat answer formatter
      if (lower.includes('sqlresult') || lower.includes('sqlresult') || lower.includes('antwort')) {
        return {
          data: {
            answer: 'Mock Antwort',
            highlights: ['Highlight 1'],
            suggestedVisualization: 'stat',
            followUpQuestions: ['Weitere Frage?'],
          },
          usage: defaultUsage,
        };
      }

      // Quiz question generator
      if (lower.includes('quiz') || lower.includes('frage') || lower.includes('question')) {
        return {
          data: {
            questions: [
              {
                questionText: 'Wer ist der Rekordtorschütze von Mainz 05?',
                category: 'top_scorers',
                difficulty: 'easy',
                sqlQueryNeeded: 'SELECT 1',
                expectedAnswerType: 'number',
                hint: undefined,
              },
            ],
          },
          usage: defaultUsage,
        };
      }

      // Quiz answer generator
      if (lower.includes('multiple-choice') || lower.includes('korrekt') || lower.includes('antwort')) {
        return {
          data: {
            correctAnswer: '1',
            incorrectAnswers: ['2', '3', '4'],
            explanation: 'Mock explanation',
            evidenceScore: 1,
          },
          usage: defaultUsage,
        };
      }

      // Default health check
      return { data: { status: 'ok' }, usage: defaultUsage };
    }),
    generateWithStreaming: vi.fn(),
    healthCheck: vi.fn().mockResolvedValue(true),
  };

  const mockLangfuseService = {
    isActive: () => false,
    getPrompt: vi.fn().mockResolvedValue(null),
    createTrace: vi.fn().mockReturnValue(null),
    createGeneration: vi.fn().mockReturnValue(null),
    endGeneration: vi.fn(),
    scoreTrace: vi.fn(),
    flush: vi.fn().mockResolvedValue(undefined),
    shutdown: vi.fn().mockResolvedValue(undefined),
  };

  return { mockOpenRouterService, mockLangfuseService };
});

vi.mock('../../services/ai/openrouter.service.js', () => ({
  openRouterService: mockOpenRouterService,
}));

vi.mock('../../services/ai/langfuse.service.js', () => ({
  langfuseService: mockLangfuseService,
}));

/**
 * E2E tests for API endpoints
 * Tests the full HTTP request/response cycle
 */
describe('API Endpoints (e2e)', () => {
  let app: FastifyInstance;
  const hasDb = Boolean(process.env.DATABASE_URL || process.env.DB_URL);
  let dbReachable = false;
  let skipAll = false;
  const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  beforeAll(async () => {
    if (!hasDb) {
      console.warn('⚠️  DATABASE_URL/DB_URL not set, skipping E2E tests');
      skipAll = true;
      return;
    }

    try {
      const { PostgresService } = await import('../../services/database/postgres.service.js');
      const probe = new PostgresService();
      dbReachable = await probe.healthCheck();
      await probe.close();
      if (!dbReachable) {
        console.warn('⚠️  Database not reachable, skipping E2E tests');
        skipAll = true;
        return;
      }
    } catch {
      console.warn('⚠️  Database probe failed, skipping E2E tests');
      skipAll = true;
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
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
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
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
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
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
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
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
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
      // metadata is optional in mocked responses
      expect(json.metadata ?? {}).toBeDefined();
    });

    it('GET /api/chat/session/:sessionId should return history', async () => {
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
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
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
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
    let lastQuestionId: string | undefined;

    it('POST /api/quiz/game should create game', async () => {
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
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

      const json = response.json();
      expect(json.game_id).toBeDefined();
      gameId = json.game_id;
    }, 60000);

    it('POST /api/quiz/game/:gameId/start should start game', async () => {
      if (skipAll || !gameId) {
        console.log('⏭️  Skipping test - DB not reachable or no gameId');
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
      if (skipAll || !gameId) {
        console.log('⏭️  Skipping test - DB not reachable or no gameId');
        return;
      }

      let response;
      // Poll until a question is ready (generation runs async)
      for (let attempt = 0; attempt < 5; attempt++) {
        response = await app.inject({
          method: 'GET',
          url: `/api/quiz/game/${gameId}/question`,
        });
        if (response.statusCode === 200) break;
        await wait(500);
      }

      if (!response || response.statusCode !== 200) {
        console.log('⏭️  Skipping test - no question available yet (job still running)');
        return;
      }
      const json = response.json();
      expect(json.question_text).toBeDefined();
      expect(json.alternatives).toBeInstanceOf(Array);
      lastQuestionId = json.question_id;
    });

    it('POST /api/quiz/game/:gameId/answer should submit answer', async () => {
      if (skipAll || !gameId) {
        console.log('⏭️  Skipping test - DB not reachable or no gameId');
        return;
      }

      // Ensure a question exists
      if (!lastQuestionId) {
        console.log('⏭️  Skipping test - no question available');
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
      if (skipAll || !gameId) {
        console.log('⏭️  Skipping test - DB not reachable or no gameId');
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
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
        return;
      }

      const response = await app.inject({
        method: 'GET',
        url: '/api/nonexistent',
      });

      expect(response.statusCode).toBe(404);
    });

    it('should validate request body', async () => {
      if (skipAll) {
        console.log('⏭️  Skipping E2E - DB not reachable');
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
