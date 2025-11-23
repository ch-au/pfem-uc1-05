import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { ChatService } from '../../services/chat/chat.service.js';
import { PostgresService } from '../../services/database/postgres.service.js';

/**
 * Integration tests for Chat Service
 * Requires:
 * - DB_URL environment variable set
 * - GEMINI_API_KEY environment variable set
 * - Database schema applied
 */
describe('ChatService (integration)', () => {
  let chatService: ChatService;
  let postgresService: PostgresService;
  let testSessionId: string;
  const hasDb = Boolean(process.env.DATABASE_URL || process.env.DB_URL);
  let dbAvailable = false;

  beforeAll(async () => {
    if (!hasDb) {
      console.warn('⚠️  DATABASE_URL/DB_URL not set, skipping integration tests');
      return;
    }
    if (!process.env.GEMINI_API_KEY && !process.env.OPENROUTER_API_KEY) {
      console.warn('⚠️  GEMINI/OPENROUTER API key not set, skipping Gemini-dependent tests');
    }
    chatService = new ChatService();
    postgresService = new PostgresService();
    try {
      dbAvailable = await postgresService.healthCheck();
      if (!dbAvailable) {
        console.warn('⚠️  Database unreachable, skipping chat integration tests');
      }
    } catch {
      dbAvailable = false;
    }
  });

  afterAll(async () => {
    // Clean up test session if created
    if (testSessionId && process.env.DB_URL) {
      try {
        await chatService.deleteSession(testSessionId);
      } catch (e) {
        // Ignore cleanup errors
      }
    }

    if (postgresService) {
      await postgresService.close();
    }
  });

  describe('Session Management', () => {
    it('should create a new chat session', async () => {
      if (!hasDb || !dbAvailable) {
        console.log('⏭️  Skipping test - no DATABASE_URL/DB_URL or DB not reachable');
        return;
      }

      const session = await chatService.createSession();

      expect(session).toBeDefined();
      expect(session.session_id).toBeDefined();
      expect(session.created_at).toBeInstanceOf(Date);
      expect(session.expires_at).toBeInstanceOf(Date);

      testSessionId = session.session_id;

      // Cleanup
      await chatService.deleteSession(session.session_id);
    });

    it('should retrieve session by ID', async () => {
      if (!hasDb || !dbAvailable) {
        console.log('⏭️  Skipping test - no DATABASE_URL/DB_URL or DB not reachable');
        return;
      }

      const session = await chatService.createSession();
      testSessionId = session.session_id;

      const retrieved = await chatService.getSession(session.session_id);

      expect(retrieved).toBeDefined();
      expect(retrieved?.session_id).toBe(session.session_id);

      await chatService.deleteSession(session.session_id);
    });

    it('should delete session and messages', async () => {
      if (!hasDb || !dbAvailable) {
        console.log('⏭️  Skipping test - no DATABASE_URL/DB_URL or DB not reachable');
        return;
      }

      const session = await chatService.createSession();

      await chatService.deleteSession(session.session_id);

      const deleted = await chatService.getSession(session.session_id);
      expect(deleted).toBeNull();
    });
  });

  describe('Message Processing (requires Gemini API)', () => {
    it.skip('should process a full chat message (requires real API keys)', async () => {
      // This test requires real Gemini API key and working database
      // Run manually with: DB_URL=... GEMINI_API_KEY=... pnpm test:integration
      expect(true).toBe(true);
    });
  });
});
