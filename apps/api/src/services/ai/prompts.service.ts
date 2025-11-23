import { readFile } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { langfuseService } from './langfuse.service.js';
import { openRouterService } from './openrouter.service.js';
import { promptsConfig, type PromptConfig } from '../../config/prompts.config.js';
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

export class PromptsService {
  /**
   * Load prompt template from Langfuse or local fallback using YAML config
   */
  private async loadPromptTemplate(promptKey: string): Promise<{ 
    system: string; 
    user: string;
    config: PromptConfig;
    meta: {
      source: 'langfuse' | 'local';
      promptName: string;
      promptLabel?: string;
      promptVersion?: string | number;
      fallbackFile?: string;
    };
  }> {
    const config = promptsConfig.getPromptConfig(promptKey);
    const defaults = promptsConfig.getDefaults();

    // Try Langfuse first if enabled
    if (defaults.langfuse_enabled && langfuseService.isActive()) {
      try {
        const promptData = await langfuseService.getPrompt(
          config.langfuse_name,
          config.langfuse_label ? undefined : undefined // TODO: Support version numbers
        );
        if (promptData) {
          console.log(`✅ Loaded prompt "${promptKey}" from Langfuse (${config.langfuse_name})`);
          // Parse prompt (format: "SYSTEM INSTRUCTION:\n...\n\nUSER PROMPT:\n...")
          const parts = promptData.prompt.split('---');
          if (parts.length === 2) {
            const systemPart = parts[0].split('USER PROMPT:')[0].replace('SYSTEM INSTRUCTION:', '').trim();
            const userPart = parts[1].trim();
            return { 
              system: systemPart, 
              user: userPart, 
              config,
              meta: {
                source: 'langfuse',
                promptName: config.langfuse_name,
                promptLabel: config.langfuse_label,
                promptVersion: (promptData as any)?.config?.version,
                fallbackFile: config.fallback_file,
              },
            };
          }
        }
      } catch (error) {
        console.warn(`⚠️  Failed to load prompt "${promptKey}" from Langfuse, falling back to local`);
      }
    }

    // Fallback to local file
    try {
      const fallbackDir = join(__dirname, defaults.fallback_dir);
      const filePath = join(fallbackDir, config.fallback_file);
      const content = await readFile(filePath, 'utf-8');
      console.log(`📁 Loaded prompt "${promptKey}" from local fallback (${config.fallback_file})`);

      // Parse local file format
      const parts = content.split('---');
      if (parts.length !== 2) {
        throw new Error(`Invalid prompt format in ${config.fallback_file}`);
      }

      const systemPart = parts[0].split('USER PROMPT:')[0].replace('SYSTEM INSTRUCTION:', '').trim();
      const userPart = parts[1].trim();

      return { 
        system: systemPart, 
        user: userPart, 
        config,
        meta: {
          source: 'local',
          promptName: config.langfuse_name,
          promptLabel: config.langfuse_label,
          fallbackFile: config.fallback_file,
        },
      };
    } catch (error) {
      throw new Error(`Failed to load prompt "${promptKey}" from both Langfuse and local fallback: ${error}`);
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
    const promptKey = 'chat-sql-generator';

    // Load prompt template with config
    const { system: systemTemplate, user: userTemplate, config, meta } = await this.loadPromptTemplate(promptKey);

    // Compile with variables
    const systemPrompt = this.compileTemplate(systemTemplate, {
      schemaContext: input.schemaContext,
    });

    const userPrompt = this.compileTemplate(userTemplate, {
      conversationHistory: JSON.stringify(input.conversationHistory, null, 2),
      userQuestion: input.userQuestion,
    });

    // Create trace
    const trace = langfuseService.createTrace('chat-sql-generation', {
      userQuestion: input.userQuestion,
      prompt_key: promptKey,
      prompt_source: meta.source,
      prompt_name: meta.promptName,
      prompt_label: meta.promptLabel,
      prompt_version: meta.promptVersion,
      prompt_fallback: meta.fallbackFile,
    });

    // Get model from config (prompt-specific or default)
    const model = promptsConfig.getModelForPrompt(promptKey);

    // Create generation
    const generation = langfuseService.createGeneration(trace, {
      name: 'openrouter-sql-generation',
      model: model,
      input: { system: systemPrompt, user: userPrompt },
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_fallback: meta.fallbackFile,
      },
    });

    // Call OpenRouter with config from YAML
    const { data, usage } = await openRouterService.generateJSON<SQLGeneratorOutput>(
      userPrompt,
      {
        model: model,
        systemInstruction: systemPrompt,
        temperature: config.llm_config.temperature,
        maxOutputTokens: config.llm_config.max_tokens,
        responseFormat: config.llm_config.response_format,
      }
    );

    // End generation (latency calculated automatically by Langfuse)
    langfuseService.endGeneration(generation, data, usage);

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
    const promptKey = 'chat-answer-formatter';

    // Load prompt template with config
    const { system: systemTemplate, user: userTemplate, config, meta } = await this.loadPromptTemplate(promptKey);

    // Compile with variables
    const systemPrompt = systemTemplate;
    const userPrompt = this.compileTemplate(userTemplate, {
      userQuestion: input.userQuestion,
      sqlQuery: input.sqlQuery,
      sqlResult: JSON.stringify(input.sqlResult, null, 2),
      rowCount: String(input.resultMetadata.rowCount),
      executionTimeMs: String(input.resultMetadata.executionTimeMs),
    });

    // Create trace
    const trace = langfuseService.createTrace('chat-answer-formatting', {
      userQuestion: input.userQuestion,
      prompt_key: promptKey,
      prompt_source: meta.source,
      prompt_name: meta.promptName,
      prompt_label: meta.promptLabel,
      prompt_version: meta.promptVersion,
      prompt_fallback: meta.fallbackFile,
    });

    // Get model from config (prompt-specific or default)
    const model = promptsConfig.getModelForPrompt(promptKey);

    // Create generation
    const generation = langfuseService.createGeneration(trace, {
      name: 'openrouter-answer-formatting',
      model: model,
      input: { system: systemPrompt, user: userPrompt },
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_fallback: meta.fallbackFile,
      },
    });

    // Call OpenRouter with config from YAML
    const { data, usage } = await openRouterService.generateJSON<AnswerFormatterOutput>(
      userPrompt,
      {
        model: model,
        systemInstruction: systemPrompt,
        temperature: config.llm_config.temperature,
        maxOutputTokens: config.llm_config.max_tokens,
        responseFormat: config.llm_config.response_format,
      }
    );

    // End generation (latency calculated automatically by Langfuse)
    langfuseService.endGeneration(generation, data, usage);

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
    const promptKey = 'quiz-question-generator';

    // Load prompt template with config
    const { system: systemTemplate, user: userTemplate, config, meta } = await this.loadPromptTemplate(promptKey);

    // Compile with variables
    const systemPrompt = this.compileTemplate(systemTemplate, {
      schemaContext: input.schemaContext,
    });

    const userPrompt = this.compileTemplate(userTemplate, {
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
      prompt_key: promptKey,
      prompt_source: meta.source,
      prompt_name: meta.promptName,
      prompt_label: meta.promptLabel,
      prompt_version: meta.promptVersion,
      prompt_fallback: meta.fallbackFile,
    });

    // Get model from config (prompt-specific or default)
    const model = promptsConfig.getModelForPrompt(promptKey);

    // Create generation
    const generation = langfuseService.createGeneration(trace, {
      name: 'openrouter-question-generation',
      model: model,
      input: { system: systemPrompt, user: userPrompt },
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_fallback: meta.fallbackFile,
      },
    });

    // Call OpenRouter with config from YAML
    const { data, usage } = await openRouterService.generateJSON<QuestionGeneratorOutput>(
      userPrompt,
      {
        model: model,
        systemInstruction: systemPrompt,
        temperature: config.llm_config.temperature,
        maxOutputTokens: config.llm_config.max_tokens,
        responseFormat: config.llm_config.response_format,
      }
    );

    // End generation (latency calculated automatically by Langfuse)
    langfuseService.endGeneration(generation, data, usage);

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
    const promptKey = 'quiz-answer-generator';

    // Load prompt template with config
    const { system: systemTemplate, user: userTemplate, config, meta } = await this.loadPromptTemplate(promptKey);

    // Compile with variables
    const systemPrompt = systemTemplate;
    const userPrompt = this.compileTemplate(userTemplate, {
      question: input.question,
      difficulty: input.difficulty,
      sqlQuery: input.sqlQuery,
      sqlResult: JSON.stringify(input.sqlResult, null, 2),
    });

    // Create trace
    const trace = langfuseService.createTrace('quiz-answer-generation', {
      question: input.question,
      difficulty: input.difficulty,
      prompt_key: promptKey,
      prompt_source: meta.source,
      prompt_name: meta.promptName,
      prompt_label: meta.promptLabel,
      prompt_version: meta.promptVersion,
      prompt_fallback: meta.fallbackFile,
    });

    // Get model from config (prompt-specific or default)
    const model = promptsConfig.getModelForPrompt(promptKey);

    // Create generation
    const generation = langfuseService.createGeneration(trace, {
      name: 'openrouter-answer-generation',
      model: model,
      input: { system: systemPrompt, user: userPrompt },
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_fallback: meta.fallbackFile,
      },
    });

    // Call OpenRouter with config from YAML
    const { data, usage } = await openRouterService.generateJSON<AnswerGeneratorOutput>(
      userPrompt,
      {
        model: model,
        systemInstruction: systemPrompt,
        temperature: config.llm_config.temperature,
        maxOutputTokens: config.llm_config.max_tokens,
        responseFormat: config.llm_config.response_format,
      }
    );

    // End generation (latency calculated automatically by Langfuse)
    langfuseService.endGeneration(generation, data, usage);

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
