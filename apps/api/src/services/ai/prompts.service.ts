import { readFile } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { langfuseService } from './langfuse.service.js';
import { geminiService } from './gemini.service.js';
import type {
  SQLGeneratorInput,
  SQLGeneratorOutput,
  AnswerFormatterInput,
  AnswerFormatterOutput,
  QuestionGeneratorInput,
  QuestionGeneratorOutput,
  AnswerGeneratorInput,
  AnswerGeneratorOutput,
} from '@fsv/shared-types';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROMPTS_DIR = join(__dirname, '../../../../../prompts/fallback');

export class PromptsService {
  /**
   * Load prompt template from Langfuse or local fallback
   */
  private async loadPromptTemplate(name: string): Promise<{ system: string; user: string }> {
    // Try Langfuse first
    if (langfuseService.isActive()) {
      try {
        const promptData = await langfuseService.getPrompt(name);
        if (promptData) {
          console.log(`✅ Loaded prompt "${name}" from Langfuse`);
          // Parse prompt (format: "SYSTEM INSTRUCTION:\n...\n\nUSER PROMPT:\n...")
          const parts = promptData.prompt.split('---');
          if (parts.length === 2) {
            const systemPart = parts[0].split('USER PROMPT:')[0].replace('SYSTEM INSTRUCTION:', '').trim();
            const userPart = parts[1].trim();
            return { system: systemPart, user: userPart };
          }
        }
      } catch (error) {
        console.warn(`⚠️  Failed to load prompt "${name}" from Langfuse, falling back to local`);
      }
    }

    // Fallback to local file
    try {
      const filePath = join(PROMPTS_DIR, `${name}.txt`);
      const content = await readFile(filePath, 'utf-8');
      console.log(`📁 Loaded prompt "${name}" from local fallback`);

      // Parse local file format
      const parts = content.split('---');
      if (parts.length !== 2) {
        throw new Error(`Invalid prompt format in ${name}.txt`);
      }

      const systemPart = parts[0].split('USER PROMPT:')[0].replace('SYSTEM INSTRUCTION:', '').trim();
      const userPart = parts[1].trim();

      return { system: systemPart, user: userPart };
    } catch (error) {
      throw new Error(`Failed to load prompt "${name}" from both Langfuse and local fallback: ${error}`);
    }
  }

  /**
   * Compile prompt template with variables
   */
  private compileTemplate(template: string, variables: Record<string, string>): string {
    let compiled = template;
    for (const [key, value] of Object.entries(variables)) {
      compiled = compiled.replaceAll(`{{${key}}}`, value);
    }
    return compiled;
  }

  /**
   * Execute Chat SQL Generator
   */
  async executeChatSQLGenerator(
    input: SQLGeneratorInput
  ): Promise<{
    result: SQLGeneratorOutput;
    traceId?: string;
    generationId?: string;
  }> {
    const promptName = 'chat-sql-generator';

    // Load prompt template
    const template = await this.loadPromptTemplate(promptName);

    // Compile with variables
    const systemPrompt = this.compileTemplate(template.system, {
      schemaContext: input.schemaContext,
    });

    const userPrompt = this.compileTemplate(template.user, {
      conversationHistory: JSON.stringify(input.conversationHistory, null, 2),
      userQuestion: input.userQuestion,
    });

    // Create trace
    const trace = langfuseService.createTrace('chat-sql-generation', {
      userQuestion: input.userQuestion,
    });

    // Create generation
    const generation = langfuseService.createGeneration(trace, {
      name: 'gemini-sql-generation',
      model: 'gemini-2.0-flash-exp',
      input: { system: systemPrompt, user: userPrompt },
    });

    // Call Gemini
    const startTime = Date.now();
    const { data, usage } = await geminiService.generateJSON<SQLGeneratorOutput>(
      userPrompt,
      {
        systemInstruction: systemPrompt,
        temperature: 0.1,
        maxOutputTokens: 2000,
      }
    );
    const latency = Date.now() - startTime;

    // End generation
    langfuseService.endGeneration(generation, data, usage, latency);

    // Flush to Langfuse
    await langfuseService.flush();

    return {
      result: data,
      traceId: trace?.id,
      generationId: generation?.id,
    };
  }

  /**
   * Execute Chat Answer Formatter
   */
  async executeChatAnswerFormatter(
    input: AnswerFormatterInput
  ): Promise<{
    result: AnswerFormatterOutput;
    traceId?: string;
    generationId?: string;
  }> {
    const promptName = 'chat-answer-formatter';

    // Load prompt template
    const template = await this.loadPromptTemplate(promptName);

    // Compile with variables
    const systemPrompt = template.system;
    const userPrompt = this.compileTemplate(template.user, {
      userQuestion: input.userQuestion,
      sqlQuery: input.sqlQuery,
      sqlResult: JSON.stringify(input.sqlResult, null, 2),
      rowCount: String(input.resultMetadata.rowCount),
      executionTimeMs: String(input.resultMetadata.executionTimeMs),
    });

    // Create trace
    const trace = langfuseService.createTrace('chat-answer-formatting', {
      userQuestion: input.userQuestion,
    });

    // Create generation
    const generation = langfuseService.createGeneration(trace, {
      name: 'gemini-answer-formatting',
      model: 'gemini-2.0-flash-exp',
      input: { system: systemPrompt, user: userPrompt },
    });

    // Call Gemini
    const startTime = Date.now();
    const { data, usage } = await geminiService.generateJSON<AnswerFormatterOutput>(
      userPrompt,
      {
        systemInstruction: systemPrompt,
        temperature: 0.7,
        maxOutputTokens: 1500,
      }
    );
    const latency = Date.now() - startTime;

    // End generation
    langfuseService.endGeneration(generation, data, usage, latency);

    // Flush to Langfuse
    await langfuseService.flush();

    return {
      result: data,
      traceId: trace?.id,
      generationId: generation?.id,
    };
  }

  /**
   * Execute Quiz Question Generator
   */
  async executeQuizQuestionGenerator(
    input: QuestionGeneratorInput
  ): Promise<{
    result: QuestionGeneratorOutput;
    traceId?: string;
    generationId?: string;
  }> {
    const promptName = 'quiz-question-generator';

    // Load prompt template
    const template = await this.loadPromptTemplate(promptName);

    // Compile with variables
    const systemPrompt = this.compileTemplate(template.system, {
      schemaContext: input.schemaContext,
    });

    const userPrompt = this.compileTemplate(template.user, {
      category: input.category,
      difficulty: input.difficulty,
      count: String(input.count),
      previousQuestions: JSON.stringify(input.previousQuestions, null, 2),
    });

    // Create trace
    const trace = langfuseService.createTrace('quiz-question-generation', {
      category: input.category,
      difficulty: input.difficulty,
      count: input.count,
    });

    // Create generation
    const generation = langfuseService.createGeneration(trace, {
      name: 'gemini-question-generation',
      model: 'gemini-2.0-flash-exp',
      input: { system: systemPrompt, user: userPrompt },
    });

    // Call Gemini
    const startTime = Date.now();
    const { data, usage } = await geminiService.generateJSON<QuestionGeneratorOutput>(
      userPrompt,
      {
        systemInstruction: systemPrompt,
        temperature: 0.8,
        maxOutputTokens: 3000,
      }
    );
    const latency = Date.now() - startTime;

    // End generation
    langfuseService.endGeneration(generation, data, usage, latency);

    // Flush to Langfuse
    await langfuseService.flush();

    return {
      result: data,
      traceId: trace?.id,
      generationId: generation?.id,
    };
  }

  /**
   * Execute Quiz Answer Generator
   */
  async executeQuizAnswerGenerator(
    input: AnswerGeneratorInput
  ): Promise<{
    result: AnswerGeneratorOutput;
    traceId?: string;
    generationId?: string;
  }> {
    const promptName = 'quiz-answer-generator';

    // Load prompt template
    const template = await this.loadPromptTemplate(promptName);

    // Compile with variables
    const systemPrompt = template.system;
    const userPrompt = this.compileTemplate(template.user, {
      question: input.question,
      difficulty: input.difficulty,
      sqlQuery: input.sqlQuery,
      sqlResult: JSON.stringify(input.sqlResult, null, 2),
    });

    // Create trace
    const trace = langfuseService.createTrace('quiz-answer-generation', {
      question: input.question,
      difficulty: input.difficulty,
    });

    // Create generation
    const generation = langfuseService.createGeneration(trace, {
      name: 'gemini-answer-generation',
      model: 'gemini-2.0-flash-exp',
      input: { system: systemPrompt, user: userPrompt },
    });

    // Call Gemini
    const startTime = Date.now();
    const { data, usage } = await geminiService.generateJSON<AnswerGeneratorOutput>(
      userPrompt,
      {
        systemInstruction: systemPrompt,
        temperature: 0.6,
        maxOutputTokens: 1000,
      }
    );
    const latency = Date.now() - startTime;

    // End generation
    langfuseService.endGeneration(generation, data, usage, latency);

    // Flush to Langfuse
    await langfuseService.flush();

    return {
      result: data,
      traceId: trace?.id,
      generationId: generation?.id,
    };
  }
}

// Singleton instance
export const promptsService = new PromptsService();
