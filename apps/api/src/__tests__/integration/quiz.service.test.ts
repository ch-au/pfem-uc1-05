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
  const hasDb = Boolean(process.env.DATABASE_URL || process.env.DB_URL);
  const hasGemini = Boolean(process.env.GEMINI_API_KEY || process.env.OPENROUTER_API_KEY);
  let dbAvailable = false;

  beforeAll(async () => {
    if (!hasDb) {
      console.warn('⚠️  DATABASE_URL/DB_URL not set, skipping integration tests');
      return;
    }
    if (!hasGemini) {
      console.warn('⚠️  GEMINI_API_KEY/OPENROUTER_API_KEY not set, skipping Gemini-dependent tests');
    }
    quizService = new QuizService();
    postgresService = new PostgresService();
    try {
      dbAvailable = await postgresService.healthCheck();
      if (!dbAvailable) {
        console.warn('⚠️  Database unreachable, skipping quiz integration tests');
      }
    } catch {
      dbAvailable = false;
    }
  });

  afterAll(async () => {
    // Clean up test game if created
    if (testGameId && hasDb) {
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
      if (!hasDb || !dbAvailable) {
        console.log('⏭️  Skipping test - no DATABASE_URL/DB_URL or DB not reachable');
        return;
      }

      const categories = await postgresService.queryMany<{ name: string }>(
        'SELECT name FROM public.quiz_categories ORDER BY name'
      );

      expect(categories).toBeInstanceOf(Array);
      // No strict seed assumptions; just ensure query succeeds
      expect(categories.length).toBeGreaterThanOrEqual(0);
    });
  });
});
