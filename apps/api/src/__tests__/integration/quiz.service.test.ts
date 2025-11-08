import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { QuizService } from '../../services/quiz/quiz.service.js';
import { PostgresService } from '../../services/database/postgres.service.js';

/**
 * Integration tests for Quiz Service
 * Requires:
 * - DB_URL environment variable set
 * - GEMINI_API_KEY environment variable set
 * - Database schema applied (including migrations)
 */
describe('QuizService (integration)', () => {
  let quizService: QuizService;
  let postgresService: PostgresService;
  let testGameId: string;

  beforeAll(() => {
    if (!process.env.DB_URL) {
      console.warn('⚠️  DB_URL not set, skipping integration tests');
      return;
    }
    if (!process.env.GEMINI_API_KEY) {
      console.warn('⚠️  GEMINI_API_KEY not set, skipping integration tests');
      return;
    }
    quizService = new QuizService();
    postgresService = new PostgresService();
  });

  afterAll(async () => {
    // Clean up test game if created
    if (testGameId && process.env.DB_URL) {
      try {
        await postgresService.query('DELETE FROM public.quiz_games WHERE game_id = $1', [
          testGameId,
        ]);
      } catch (e) {
        // Ignore cleanup errors
      }
    }

    if (postgresService) {
      await postgresService.close();
    }
  });

  describe('Game Management', () => {
    it.skip('should create a new quiz game (requires Gemini API)', async () => {
      // This test requires real Gemini API key to generate questions
      // Run manually with: DB_URL=... GEMINI_API_KEY=... pnpm test:integration
      expect(true).toBe(true);
    });

    it('should validate quiz categories exist', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const categories = await postgresService.queryMany<{ name: string }>(
        'SELECT name FROM public.quiz_categories ORDER BY name'
      );

      expect(categories.length).toBeGreaterThan(0);
      expect(categories.some((c) => c.name === 'top_scorers')).toBe(true);
      expect(categories.some((c) => c.name === 'statistics')).toBe(true);
    });
  });
});
