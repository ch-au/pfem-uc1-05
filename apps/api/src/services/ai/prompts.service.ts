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
   * Returns: { system, user, config, meta }
   * - system: The prompt template (either from Langfuse or local file)
   * - user: Empty string (user content comes from method parameters, not the template)
   * - config: Prompt configuration from YAML
   * - meta: Metadata about the prompt source
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
      promptId?: string;
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
          config.langfuse_label ? undefined : undefined
        );
        if (promptData && promptData.prompt) {
          console.log(`✅ Loaded prompt "${promptKey}" from Langfuse (${config.langfuse_name})`);
          
          // Langfuse prompts are text prompts that become the system prompt
          // Remove "SYSTEM INSTRUCTION:" prefix if present
          const systemPrompt = promptData.prompt
            .replace(/^SYSTEM INSTRUCTION:\s*/i, '')
            .trim();
          
          if (systemPrompt) {
            return { 
              system: systemPrompt, 
              user: '', // User content comes from method parameters
              config,
              meta: {
                source: 'langfuse',
                promptName: config.langfuse_name,
                promptLabel: config.langfuse_label,
                promptVersion: (promptData as any)?.version ?? (promptData as any)?.config?.version,
                promptId: (promptData as any)?.id,
                fallbackFile: config.fallback_file,
              },
            };
          }
        }
      } catch (error) {
        console.warn(`⚠️  Failed to load prompt "${promptKey}" from Langfuse:`, error);
        console.warn(`    Falling back to local prompt`);
      }
    }

    // Fallback to local file
    try {
      const fallbackDir = join(__dirname, defaults.fallback_dir);
      const filePath = join(fallbackDir, config.fallback_file);
      const content = await readFile(filePath, 'utf-8');
      console.log(`📁 Loaded prompt "${promptKey}" from local fallback (${config.fallback_file})`);

      // Local prompts are text prompts that become the system prompt
      // Remove "SYSTEM INSTRUCTION:" prefix if present
      const systemPrompt = content
        .replace(/^SYSTEM INSTRUCTION:\s*/i, '')
        .trim();

      if (!systemPrompt) {
        throw new Error(`Invalid prompt format in ${config.fallback_file} - no content found`);
      }

      return { 
        system: systemPrompt, 
        user: '', // User content comes from method parameters
        config,
        meta: {
          source: 'local',
          promptName: config.langfuse_name,
          promptLabel: config.langfuse_label,
          promptVersion: config.langfuse_label || 'fallback',
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
    const { system: systemTemplate, config, meta } = await this.loadPromptTemplate(promptKey);

    // Compile system prompt with variables
    const systemPrompt = this.compileTemplate(systemTemplate, {
      schemaContext: input.schemaContext,
    });

    // Construct user prompt from input parameters
    const userPrompt = `Conversation History:\n${JSON.stringify(input.conversationHistory, null, 2)}\n\nUser Question:\n${input.userQuestion}`;

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

    // Fetch the prompt object from Langfuse to link it to the generation
    const langfusePrompt = await langfuseService.getPrompt(meta.promptName,
      meta.promptVersion && meta.promptVersion !== 'fallback' ? Number(meta.promptVersion) : undefined
    );

    // Create generation with direct prompt link
    const generation = langfuseService.createGenerationWithPrompt(trace, {
      name: 'SQL Query Generation',
      model: model,
      input: { system: systemPrompt, user: userPrompt },
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_id: meta.promptId,
        prompt_fallback: meta.fallbackFile,
      },
      langfusePrompt: langfusePrompt,
      promptName: meta.promptName,
      promptVersion: meta.promptVersion,
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
    const { system: systemTemplate, config, meta } = await this.loadPromptTemplate(promptKey);

    // Compile system prompt
    const systemPrompt = systemTemplate;
    
    // Construct user prompt from input parameters
    const userPrompt = `User Question:\n${input.userQuestion}\n\nSQL Query:\n${input.sqlQuery}\n\nSQL Result:\n${JSON.stringify(input.sqlResult, null, 2)}\n\nResult Metadata:\n- Row Count: ${input.resultMetadata.rowCount}\n- Execution Time: ${input.resultMetadata.executionTimeMs}ms`;

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

    // Fetch the prompt object from Langfuse to link it to the generation
    const langfusePrompt = await langfuseService.getPrompt(meta.promptName,
      meta.promptVersion && meta.promptVersion !== 'fallback' ? Number(meta.promptVersion) : undefined
    );

    // Create generation with direct prompt link
    const generation = langfuseService.createGenerationWithPrompt(trace, {
      name: 'Answer Formatting',
      model: model,
      input: { system: systemPrompt, user: userPrompt },
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_id: meta.promptId,
        prompt_fallback: meta.fallbackFile,
      },
      langfusePrompt: langfusePrompt,
      promptName: meta.promptName,
      promptVersion: meta.promptVersion,
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
    const { system: systemTemplate, config, meta } = await this.loadPromptTemplate(promptKey);

    // Compile system prompt with variables
    const systemPrompt = this.compileTemplate(systemTemplate, {
      schemaContext: input.schemaContext,
    });

    // Construct user prompt from input parameters
    const userPrompt = `Category: ${input.category}\nDifficulty: ${input.difficulty}\nNumber of Questions: ${input.count}\n\nPrevious Questions (to avoid duplicates):\n${JSON.stringify(input.previousQuestions, null, 2)}`;

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

    // Fetch the prompt object from Langfuse to link it to the generation
    const langfusePrompt = await langfuseService.getPrompt(meta.promptName, 
      meta.promptVersion && meta.promptVersion !== 'fallback' ? Number(meta.promptVersion) : undefined
    );

    // Create generation with direct prompt link
    const generation = langfuseService.createGenerationWithPrompt(trace, {
      name: 'Quiz Question Generation',
      model: model,
      input: { system: systemPrompt, user: userPrompt },
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_id: meta.promptId,
        prompt_fallback: meta.fallbackFile,
      },
      langfusePrompt: langfusePrompt,
      promptName: meta.promptName,
      promptVersion: meta.promptVersion,
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
    const { system: systemTemplate, config, meta } = await this.loadPromptTemplate(promptKey);

    // Compile system prompt
    const systemPrompt = systemTemplate;
    
    // Construct user prompt from input parameters
    const userPrompt = `Question: ${input.question}\nDifficulty: ${input.difficulty}\n\nSQL Query:\n${input.sqlQuery}\n\nSQL Result:\n${JSON.stringify(input.sqlResult, null, 2)}`;

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

    // Fetch the prompt object from Langfuse to link it to the generation
    const langfusePrompt = await langfuseService.getPrompt(meta.promptName,
      meta.promptVersion && meta.promptVersion !== 'fallback' ? Number(meta.promptVersion) : undefined
    );

    // Create generation with direct prompt link
    const generation = langfuseService.createGenerationWithPrompt(trace, {
      name: 'Quiz Answer Generation',
      model: model,
      input: { system: systemPrompt, user: userPrompt },
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_id: meta.promptId,
        prompt_fallback: meta.fallbackFile,
      },
      langfusePrompt: langfusePrompt,
      promptName: meta.promptName,
      promptVersion: meta.promptVersion,
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
