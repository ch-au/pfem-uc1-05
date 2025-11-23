import { Langfuse, type LangfuseTraceClient, type LangfuseGenerationClient } from 'langfuse';
import { env, isLangfuseAvailable } from '../../config/env.js';

export interface PromptConfig {
  name: string;
  version?: number;
  variables: Record<string, string>;
}

export class LangfuseService {
  private langfuse: Langfuse | null = null;
  private isEnabled: boolean;

  constructor() {
    this.isEnabled = isLangfuseAvailable();

    if (this.isEnabled) {
      this.langfuse = new Langfuse({
        publicKey: env.LANGFUSE_PUBLIC_KEY!,
        secretKey: env.LANGFUSE_SECRET_KEY!,
        baseUrl: env.LANGFUSE_HOST,
        flushAt: 1, // Flush after each event in development
        flushInterval: 1000, // Flush every second
      });

      console.log('✅ Langfuse tracing enabled');
    } else {
      console.log('⚠️  Langfuse not configured - using local fallback prompts');
    }
  }

  /**
   * Get a prompt from Langfuse
   * Returns the actual prompt object for linking to generations
   */
  async getPrompt(name: string, version?: number): Promise<any> {
    if (!this.isEnabled || !this.langfuse) {
      return null;
    }

    try {
      const prompt = await this.langfuse.getPrompt(name, version);
      return prompt;
    } catch (error) {
      console.error(`Failed to fetch prompt "${name}" from Langfuse:`, error);
      return null;
    }
  }

  /**
   * Create a trace for tracking AI operations
   */
  createTrace(
    name: string,
    config?: {
      input?: any;
      metadata?: Record<string, any>;
    }
  ): LangfuseTraceClient | null {
    if (!this.isEnabled || !this.langfuse) {
      return null;
    }

    return this.langfuse.trace({
      name,
      input: config?.input,
      metadata: config?.metadata,
      timestamp: new Date(),
    });
  }

  /**
   * End a trace with output
   */
  endTrace(trace: LangfuseTraceClient | null, output?: any): void {
    if (!trace) {
      return;
    }

    trace.end({
      output,
    });
  }

  /**
   * Create a generation within a trace
   */
  createGeneration(
    trace: LangfuseTraceClient | null,
    config: {
      name: string;
      model: string;
      input: any;
      metadata?: Record<string, any>;
      promptId?: string;
      promptName?: string;
      promptVersion?: string | number;
    }
  ): LangfuseGenerationClient | null {
    if (!trace) {
      return null;
    }

    return trace.generation({
      name: config.name,
      model: config.model,
      input: config.input,
      metadata: config.metadata,
      prompt: config.promptId
        ? { id: config.promptId }
        : config.promptName
        ? { name: config.promptName, version: config.promptVersion }
        : undefined,
    });
  }

  /**
   * Create a generation with explicit prompt object linking
   */
  createGenerationWithPrompt(
    trace: LangfuseTraceClient | null,
    config: {
      name: string;
      model: string;
      input: any;
      metadata?: Record<string, any>;
      langfusePrompt?: any;
      promptName?: string;
      promptVersion?: string | number;
    }
  ): LangfuseGenerationClient | null {
    if (!trace) {
      return null;
    }

    // Pass the actual Langfuse prompt object directly if available
    return trace.generation({
      name: config.name,
      model: config.model,
      input: config.input,
      metadata: config.metadata,
      prompt: config.langfusePrompt ? config.langfusePrompt : undefined,
    });
  }

  /**
   * End a generation with output and usage stats
   * Note: Latency is calculated automatically by Langfuse from start/end timestamps
   */
  endGeneration(
    generation: LangfuseGenerationClient | null,
    output: any,
    usage: { promptTokens: number; completionTokens: number; totalTokens: number }
  ): void {
    if (!generation) {
      return;
    }

    generation.end({
      output,
      usage: {
        promptTokens: usage.promptTokens,
        completionTokens: usage.completionTokens,
        totalTokens: usage.totalTokens,
      },
    });
  }

  /**
   * Score a trace (for feedback)
   */
  scoreTrace(
    traceId: string,
    name: string,
    value: number,
    comment?: string
  ): void {
    if (!this.isEnabled || !this.langfuse) {
      return;
    }

    this.langfuse.score({
      traceId,
      name,
      value,
      comment,
    });
  }

  /**
   * Flush all pending events to Langfuse
   */
  async flush(): Promise<void> {
    if (!this.isEnabled || !this.langfuse) {
      return;
    }

    await this.langfuse.flushAsync();
  }

  /**
   * Shutdown Langfuse client
   */
  async shutdown(): Promise<void> {
    if (!this.isEnabled || !this.langfuse) {
      return;
    }

    await this.langfuse.shutdownAsync();
  }

  /**
   * Check if Langfuse is enabled and working
   */
  isActive(): boolean {
    return this.isEnabled;
  }
}

// Singleton instance
export const langfuseService = new LangfuseService();
