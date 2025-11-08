import { OpenRouter } from '@openrouter/sdk';
import { env } from '../../config/env.js';

export interface OpenRouterGenerateOptions {
  systemInstruction?: string;
  temperature?: number;
  maxOutputTokens?: number;
  responseFormat?: 'json' | 'text';
  responseSchema?: Record<string, any>;
}

export interface OpenRouterUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export class OpenRouterService {
  private client: OpenRouter;

  constructor() {
    this.client = new OpenRouter({
      apiKey: env.OPENROUTER_API_KEY,
    });
  }

  /**
   * Generate JSON content from OpenRouter API
   */
  async generateJSON<T = any>(
    prompt: string,
    options: OpenRouterGenerateOptions = {}
  ): Promise<{ data: T; usage: OpenRouterUsage }> {
    const messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }> = [];

    if (options.systemInstruction) {
      messages.push({
        role: 'system',
        content: options.systemInstruction,
      });
    }

    messages.push({
      role: 'user',
      content: prompt,
    });

    const response = await this.client.chat.send({
      model: env.OPENROUTER_MODEL,
      messages,
      temperature: options.temperature ?? 0.7,
      maxTokens: options.maxOutputTokens ?? 2000,
      responseFormat: options.responseFormat === 'json' ? { type: 'json_object' } : undefined,
    });

    const content = response.choices[0]?.message?.content;
    const contentStr = typeof content === 'string' ? content : JSON.stringify(content) || '{}';

    // Parse JSON response
    let data: T;
    try {
      data = JSON.parse(contentStr) as T;
    } catch (error) {
      throw new Error(`Failed to parse OpenRouter JSON response: ${contentStr.substring(0, 200)}...`);
    }

    // Extract usage metadata
    const usage: OpenRouterUsage = {
      promptTokens: response.usage?.promptTokens ?? 0,
      completionTokens: response.usage?.completionTokens ?? 0,
      totalTokens: response.usage?.totalTokens ?? 0,
    };

    return { data, usage };
  }

  /**
   * Generate content with streaming support
   */
  async generateWithStreaming(
    prompt: string,
    onChunk: (chunk: string) => void,
    options: OpenRouterGenerateOptions = {}
  ): Promise<void> {
    const messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }> = [];

    if (options.systemInstruction) {
      messages.push({
        role: 'system',
        content: options.systemInstruction,
      });
    }

    messages.push({
      role: 'user',
      content: prompt,
    });

    const stream = await this.client.chat.send({
      model: env.OPENROUTER_MODEL,
      messages,
      temperature: options.temperature ?? 0.7,
      maxTokens: options.maxOutputTokens ?? 2000,
      stream: true,
    });

    for await (const chunk of stream) {
      const content = chunk.choices[0]?.delta?.content;
      if (content) {
        onChunk(content);
      }
    }
  }

  /**
   * Health check for OpenRouter API
   */
  async healthCheck(): Promise<boolean> {
    try {
      const { data } = await this.generateJSON<{ status: string }>(
        'Respond with {"status": "ok"}',
        {
          temperature: 0,
          maxOutputTokens: 50,
          responseFormat: 'json',
        }
      );
      return data.status === 'ok';
    } catch (error) {
      console.error('OpenRouter health check failed:', error);
      return false;
    }
  }
}

// Singleton instance
export const openRouterService = new OpenRouterService();
