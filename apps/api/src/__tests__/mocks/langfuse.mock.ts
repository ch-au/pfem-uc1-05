import { vi } from 'vitest';

/**
 * Mock Langfuse trace
 */
export const createMockTrace = () => ({
  id: 'trace-mock-id',
  generation: vi.fn().mockReturnValue(createMockGeneration()),
});

/**
 * Mock Langfuse generation
 */
export const createMockGeneration = () => ({
  id: 'generation-mock-id',
  end: vi.fn(),
});

/**
 * Create a mock Langfuse service
 */
export const createMockLangfuseService = (isActive = true) => {
  return {
    getPrompt: vi.fn().mockResolvedValue(null), // Force fallback to local prompts
    createTrace: vi.fn().mockReturnValue(isActive ? createMockTrace() : null),
    createGeneration: vi.fn().mockReturnValue(isActive ? createMockGeneration() : null),
    endGeneration: vi.fn(),
    scoreTrace: vi.fn(),
    flush: vi.fn().mockResolvedValue(undefined),
    shutdown: vi.fn().mockResolvedValue(undefined),
    isActive: vi.fn().mockReturnValue(isActive),
  };
};
