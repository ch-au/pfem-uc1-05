import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { PostgresService } from '../../services/database/postgres.service.js';

/**
 * Integration tests for PostgreSQL service
 * Requires a running PostgreSQL database with the schema applied
 */
describe('PostgresService (integration)', () => {
  let postgresService: PostgresService;

  beforeAll(() => {
    // Check if DB_URL is set
    if (!process.env.DB_URL) {
      console.warn('⚠️  DB_URL not set, skipping integration tests');
      return;
    }
    postgresService = new PostgresService();
  });

  afterAll(async () => {
    if (postgresService) {
      await postgresService.close();
    }
  });

  describe('healthCheck', () => {
    it('should connect to database successfully', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const result = await postgresService.healthCheck();
      expect(result).toBe(true);
    });
  });

  describe('query operations', () => {
    it('should execute a simple SELECT query', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const result = await postgresService.query('SELECT 1 as test');
      expect(result.rows).toHaveLength(1);
      expect(result.rows[0].test).toBe(1);
    });

    it('should fetch quiz categories', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const result = await postgresService.queryMany<{ name: string }>(
        'SELECT name FROM public.quiz_categories ORDER BY name LIMIT 5'
      );

      expect(result).toBeInstanceOf(Array);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0]).toHaveProperty('name');
    });

    it('should use queryOne to fetch single row', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const result = await postgresService.queryOne<{ count: string }>(
        "SELECT COUNT(*) as count FROM public.quiz_categories WHERE name = 'top_scorers'"
      );

      expect(result).toBeDefined();
      expect(result?.count).toBe('1');
    });
  });

  describe('executeUserQuery (SQL safety)', () => {
    it('should execute safe SELECT query', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const { rows, executionTimeMs } = await postgresService.executeUserQuery(
        'SELECT COUNT(*) as total FROM public.quiz_categories'
      );

      expect(rows).toBeInstanceOf(Array);
      expect(executionTimeMs).toBeGreaterThan(0);
    });

    it('should reject non-SELECT queries', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      await expect(
        postgresService.executeUserQuery('DELETE FROM public.quiz_categories WHERE name = "test"')
      ).rejects.toThrow('Only SELECT statements are allowed');
    });

    it('should reject INSERT queries', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      await expect(
        postgresService.executeUserQuery(
          "INSERT INTO public.quiz_categories (name) VALUES ('malicious')"
        )
      ).rejects.toThrow('Only SELECT statements are allowed');
    });

    it('should reject UPDATE queries', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      await expect(
        postgresService.executeUserQuery(
          "UPDATE public.quiz_categories SET name = 'hacked' WHERE name = 'test'"
        )
      ).rejects.toThrow('Only SELECT statements are allowed');
    });
  });

  describe('transaction support', () => {
    it('should execute transaction successfully', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      const result = await postgresService.transaction(async (client) => {
        const res = await client.query('SELECT COUNT(*) as count FROM public.quiz_categories');
        return res.rows[0].count;
      });

      expect(result).toBeDefined();
      expect(typeof result).toBe('string');
    });

    it('should rollback on error', async () => {
      if (!process.env.DB_URL) {
        console.log('⏭️  Skipping test - no DB_URL');
        return;
      }

      await expect(
        postgresService.transaction(async (client) => {
          await client.query('SELECT 1');
          throw new Error('Test error');
        })
      ).rejects.toThrow('Test error');
    });
  });
});
