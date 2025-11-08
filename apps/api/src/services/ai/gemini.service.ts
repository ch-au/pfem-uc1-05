import { GoogleGenerativeAI, GenerativeModel, GenerationConfig } from '@google/generative-ai';
import { env } from '../../config/env.js';

export interface GeminiGenerateOptions {
  systemInstruction?: string;
  temperature?: number;
  maxOutputTokens?: number;
  responseFormat?: 'json' | 'text';
}

export class GeminiService {
  private genAI: GoogleGenerativeAI;
  private models: Map<string, GenerativeModel> = new Map();

  constructor() {
    this.genAI = new GoogleGenerativeAI(env.GEMINI_API_KEY);
  }

  private getModel(modelName: string = env.GEMINI_MODEL): GenerativeModel {
    if (!this.models.has(modelName)) {
      this.models.set(modelName, this.genAI.getGenerativeModel({ model: modelName }));
    }
    return this.models.get(modelName)!;
  }

  /**
   * Generate content from Gemini API with JSON response
   */
  async generateJSON<T = any>(
    prompt: string,
    options: GeminiGenerateOptions = {}
  ): Promise<{ data: T; usage: { promptTokens: number; completionTokens: number; totalTokens: number } }> {
    const model = this.getModel();

    const generationConfig: GenerationConfig = {
      temperature: options.temperature ?? 0.7,
      maxOutputTokens: options.maxOutputTokens ?? 2000,
      responseMimeType: 'application/json',
    };

    const chatSession = model.startChat({
      generationConfig,
      ...(options.systemInstruction && {
        systemInstruction: options.systemInstruction,
      }),
    });

    const result = await chatSession.sendMessage(prompt);
    const response = result.response;
    const text = response.text();

    // Parse JSON response
    let data: T;
    try {
      data = JSON.parse(text) as T;
    } catch (error) {
      throw new Error(`Failed to parse Gemini JSON response: ${text.substring(0, 200)}...`);
    }

    // Extract usage metadata (if available)
    const usage = {
      promptTokens: response.usageMetadata?.promptTokenCount ?? 0,
      completionTokens: response.usageMetadata?.candidatesTokenCount ?? 0,
      totalTokens: response.usageMetadata?.totalTokenCount ?? 0,
    };

    return { data, usage };
  }

  /**
   * Generate content with streaming support
   */
  async generateWithStreaming(
    prompt: string,
    onChunk: (chunk: string) => void,
    options: GeminiGenerateOptions = {}
  ): Promise<void> {
    const model = this.getModel();

    const result = await model.generateContentStream({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: options.temperature ?? 0.7,
        maxOutputTokens: options.maxOutputTokens ?? 2000,
      },
      ...(options.systemInstruction && {
        systemInstruction: { parts: [{ text: options.systemInstruction }] },
      }),
    });

    for await (const chunk of result.stream) {
      const chunkText = chunk.text();
      onChunk(chunkText);
    }
  }

  /**
   * Health check for Gemini API
   */
  async healthCheck(): Promise<boolean> {
    try {
      const { data } = await this.generateJSON<{ status: string }>(
        'Respond with {"status": "ok"}',
        {
          temperature: 0,
          maxOutputTokens: 50,
        }
      );
      return data.status === 'ok';
    } catch (error) {
      console.error('Gemini health check failed:', error);
      return false;
    }
  }
}

// Singleton instance
export const geminiService = new GeminiService();
