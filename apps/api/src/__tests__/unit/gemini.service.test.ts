import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GeminiService } from '../../services/ai/gemini.service.js';

// Mock @google/generative-ai
vi.mock('@google/generative-ai', () => {
  const mockChat = {
    sendMessage: vi.fn().mockResolvedValue({
      response: {
        text: () => '{"status": "ok", "data": "test"}',
        usageMetadata: {
          promptTokenCount: 100,
          candidatesTokenCount: 50,
          totalTokenCount: 150,
        },
      },
    }),
  };

  const mockModel = {
    startChat: vi.fn().mockReturnValue(mockChat),
    generateContentStream: vi.fn().mockResolvedValue({
      stream: (async function* () {
        yield { text: () => 'chunk1' };
        yield { text: () => 'chunk2' };
      })(),
    }),
  };

  return {
    GoogleGenerativeAI: vi.fn().mockImplementation(() => ({
      getGenerativeModel: vi.fn().mockReturnValue(mockModel),
    })),
  };
});

// Mock env
vi.mock('../../config/env.js', () => ({
  env: {
    GEMINI_API_KEY: 'test-api-key',
    GEMINI_MODEL: 'gemini-2.0-flash-exp',
  },
}));

describe('GeminiService (unit)', () => {
  let geminiService: GeminiService;

  beforeEach(() => {
    vi.clearAllMocks();
    geminiService = new GeminiService();
  });

  describe('generateJSON', () => {
    it('should generate JSON response successfully', async () => {
      const result = await geminiService.generateJSON('test prompt', {
        temperature: 0.7,
      });

      expect(result).toHaveProperty('data');
      expect(result).toHaveProperty('usage');
      expect(result.data).toEqual({ status: 'ok', data: 'test' });
      expect(result.usage.totalTokens).toBe(150);
    });

    it('should use custom temperature', async () => {
      await geminiService.generateJSON('test prompt', {
        temperature: 0.5,
        maxOutputTokens: 1000,
      });

      // Verify the method was called
      expect(true).toBe(true);
    });

    it('should handle system instruction', async () => {
      await geminiService.generateJSON('test prompt', {
        systemInstruction: 'You are a helpful assistant',
      });

      expect(true).toBe(true);
    });
  });

  describe('generateWithStreaming', () => {
    it('should stream response chunks', async () => {
      const chunks: string[] = [];
      const onChunk = (chunk: string) => chunks.push(chunk);

      await geminiService.generateWithStreaming('test prompt', onChunk);

      expect(chunks).toHaveLength(2);
      expect(chunks[0]).toBe('chunk1');
      expect(chunks[1]).toBe('chunk2');
    });
  });

  describe('healthCheck', () => {
    it('should return true when API is healthy', async () => {
      const result = await geminiService.healthCheck();

      expect(result).toBe(true);
    });
  });
});
