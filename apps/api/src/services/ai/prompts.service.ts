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

/**
 * Normalize LLM answer generation output to handle both German and English field names.
 * Maps various field name aliases to the canonical English schema.
 */
// Helper to find first matching key from aliases
function findValue(obj: any, aliases: string[]): any {
  for (const alias of aliases) {
    if (obj[alias] !== undefined) return obj[alias];
  }
  return undefined;
}

/**
 * Normalize a single question object from LLM output.
 * Maps various field name aliases to the canonical English schema.
 */
function normalizeQuestion(raw: any): { 
  questionText: string; 
  sqlQueryNeeded: string;
  category?: string;
  difficulty?: 'easy' | 'medium' | 'hard';
} {
  if (!raw || typeof raw !== 'object') {
    throw new Error(`Invalid question object: expected object, got ${typeof raw}`);
  }

  // Field name aliases for questionText
  const questionTextAliases = [
    'questionText', 'question_text', 'question',
    'Fragetext', 'fragetext', 'Frage', 'frage',
    'FrageText', 'text', 'Text'
  ];
  
  // Field name aliases for sqlQueryNeeded
  const sqlQueryAliases = [
    'sqlQueryNeeded', 'sql_query_needed', 'sqlQuery', 'sql_query',
    'sql', 'SQL', 'query', 'Query',
    'SQL_Abfrage', 'sql_abfrage', 'SQLAbfrage',
    'benötigte_sql_abfrage', 'BenotigteSQL'
  ];

  // Field name aliases for category (optional)
  const categoryAliases = ['category', 'Kategorie', 'kategorie', 'topic', 'Thema'];
  
  // Field name aliases for difficulty (optional)
  const difficultyAliases = ['difficulty', 'Schwierigkeit', 'schwierigkeit', 'level'];

  const questionText = findValue(raw, questionTextAliases);
  const sqlQueryNeeded = findValue(raw, sqlQueryAliases);
  const category = findValue(raw, categoryAliases);
  const difficulty = findValue(raw, difficultyAliases);

  if (!questionText) {
    console.error('   ⚠️ Missing questionText in question. Raw:', JSON.stringify(raw, null, 2));
    throw new Error('Question missing questionText field');
  }

  if (!sqlQueryNeeded) {
    console.error('   ⚠️ Missing sqlQueryNeeded in question. Raw:', JSON.stringify(raw, null, 2));
    throw new Error('Question missing sqlQueryNeeded field');
  }

  return {
    questionText: String(questionText),
    sqlQueryNeeded: String(sqlQueryNeeded),
    category: category ? String(category) : undefined,
    difficulty: difficulty as 'easy' | 'medium' | 'hard' | undefined,
  };
}

/**
 * Normalize LLM question generator output to handle both German and English field names.
 */
function normalizeQuestionGeneratorOutput(raw: any): QuestionGeneratorOutput {
  if (!raw || typeof raw !== 'object') {
    throw new Error(`Invalid question generator response: expected object, got ${typeof raw}`);
  }

  // Field name aliases for questions array
  const questionsAliases = ['questions', 'Fragen', 'fragen', 'questionList', 'question_list'];
  
  const questionsRaw = findValue(raw, questionsAliases);
  
  if (!questionsRaw || !Array.isArray(questionsRaw)) {
    console.error('   ⚠️ Missing or invalid questions array in LLM response. Raw:', JSON.stringify(raw, null, 2));
    throw new Error('LLM response missing questions array');
  }

  // Normalize each question
  const questions = questionsRaw.map((q: any, idx: number) => {
    try {
      return normalizeQuestion(q);
    } catch (err) {
      console.error(`   ⚠️ Failed to normalize question ${idx + 1}:`, err);
      throw err;
    }
  });

  return { questions };
}

function normalizeAnswerGeneratorOutput(raw: any): AnswerGeneratorOutput {
  if (!raw || typeof raw !== 'object') {
    throw new Error(`Invalid answer generator response: expected object, got ${typeof raw}`);
  }

  // Field name aliases (German -> English)
  const correctAnswerAliases = ['correctAnswer', 'correct_answer', 'Richtige_Antwort', 'richtige_antwort', 'answer', 'Antwort'];
  const incorrectAnswersAliases = ['incorrectAnswers', 'incorrect_answers', 'Falsche_Antworten', 'falsche_antworten', 'wrongAnswers', 'wrong_answers'];
  const explanationAliases = ['explanation', 'Erklärung', 'erklaerung', 'Erklaerung'];
  const evidenceScoreAliases = ['evidenceScore', 'evidence_score', 'Bewertung', 'bewertung', 'confidence', 'score'];
  const optionsAliases = ['options', 'Antwortmöglichkeiten', 'antwortmoeglichkeiten', 'alternatives', 'choices'];

  // Extract correct answer
  let correctAnswer = findValue(raw, correctAnswerAliases);
  
  // Extract incorrect answers
  let incorrectAnswers = findValue(raw, incorrectAnswersAliases);
  
  // If no incorrectAnswers but we have options array, derive incorrect answers
  if (!incorrectAnswers && findValue(raw, optionsAliases)) {
    const options = findValue(raw, optionsAliases);
    if (Array.isArray(options) && correctAnswer) {
      // Filter out the correct answer from options to get incorrect ones
      incorrectAnswers = options.filter((opt: string) => 
        opt !== correctAnswer && 
        opt?.toLowerCase?.() !== correctAnswer?.toLowerCase?.()
      );
    }
  }

  // Extract explanation and evidence score
  const explanation = findValue(raw, explanationAliases) ?? '';
  const evidenceScore = findValue(raw, evidenceScoreAliases) ?? 0.5;

  // Validate required fields
  if (!correctAnswer) {
    console.error('   ⚠️ Missing correctAnswer in LLM response. Raw data:', JSON.stringify(raw, null, 2));
    throw new Error('LLM response missing correctAnswer field');
  }

  if (!incorrectAnswers || !Array.isArray(incorrectAnswers) || incorrectAnswers.length === 0) {
    console.error('   ⚠️ Missing or invalid incorrectAnswers in LLM response. Raw data:', JSON.stringify(raw, null, 2));
    throw new Error('LLM response missing or invalid incorrectAnswers field');
  }

  // Ensure we have exactly 3 incorrect answers (pad or trim if needed)
  if (incorrectAnswers.length < 3) {
    console.warn(`   ⚠️ Only ${incorrectAnswers.length} incorrect answers provided, expected 3`);
  }
  if (incorrectAnswers.length > 3) {
    incorrectAnswers = incorrectAnswers.slice(0, 3);
  }

  return {
    correctAnswer: String(correctAnswer),
    incorrectAnswers: incorrectAnswers.map((a: any) => String(a)),
    explanation: String(explanation),
    evidenceScore: typeof evidenceScore === 'number' ? evidenceScore : parseFloat(evidenceScore) || 0.5,
  };
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export class PromptsService {
  /**
   * Load prompt template from Langfuse or local fallback using YAML config
   * Handles two formats:
   * 1. Chat prompts: Only "SYSTEM INSTRUCTION: ..." (no separator)
   * 2. Chat prompts with templates: "SYSTEM INSTRUCTION: ...\n\n---\n\nUSER PROMPT: ..."
   * Returns: { system, user, config, meta }
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
          
          const result = this.parsePromptTemplate(promptData.prompt);
          
          if (result) {
            return { 
              ...result,
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

      const result = this.parsePromptTemplate(content);
      
      if (result) {
        return { 
          ...result,
          config,
          meta: {
            source: 'local',
            promptName: config.langfuse_name,
            promptLabel: config.langfuse_label,
            promptVersion: config.langfuse_label || 'fallback',
            fallbackFile: config.fallback_file,
          },
        };
      }

      throw new Error(`Invalid prompt format in ${config.fallback_file} - no content found`);
    } catch (error) {
      throw new Error(`Failed to load prompt "${promptKey}" from both Langfuse and local fallback: ${error}`);
    }
  }

  /**
   * Parse prompt template - handles two formats:
   * 1. Simple text: "SYSTEM INSTRUCTION: ..." -> becomes system prompt
   * 2. Chat template: "SYSTEM INSTRUCTION: ...\n\n---\n\nUSER PROMPT: ..." -> split into system and user
   */
  private parsePromptTemplate(content: string): { system: string; user: string } | null {
    // Check if this is a chat template with USER PROMPT section
    if (content.includes('---') && content.includes('USER PROMPT:')) {
      const parts = content.split('---');
      if (parts.length >= 2) {
        const systemPart = parts[0]
          .replace(/^SYSTEM INSTRUCTION:\s*/i, '')
          .trim();
        
        const userPart = parts[1]
          .replace(/^USER PROMPT:\s*/i, '')
          .trim();
        
        if (systemPart && userPart) {
          return { system: systemPart, user: userPart };
        }
      }
    }
    
    // Otherwise treat entire content as system prompt
    const systemPrompt = content
      .replace(/^SYSTEM INSTRUCTION:\s*/i, '')
      .trim();
    
    if (systemPrompt) {
      return { system: systemPrompt, user: '' };
    }
    
    return null;
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
    console.log(`\n🔍 [SQL GENERATOR] Starting SQL generation...`);
    console.log(`   Question: "${input.userQuestion}"`);
    
    const promptKey = 'chat-sql-generator';

    // Load prompt template with config
    const { system: systemTemplate, user: userTemplate, config, meta } = await this.loadPromptTemplate(promptKey);
    console.log(`   ✓ Loaded prompt template from ${meta.source}`);

    // Format conversation history for the prompt
    const formattedHistory = input.conversationHistory && input.conversationHistory.length > 0
      ? input.conversationHistory.map((msg) => `${msg.role === 'user' ? 'Nutzer' : 'Assistent'}: ${msg.content}`).join('\n')
      : 'Keine vorherige Konversation.';
    
    console.log(`   📝 Conversation history (${input.conversationHistory?.length || 0} messages):`);
    console.log(`   ${formattedHistory.substring(0, 500)}...`);

    // Compile system prompt with Kontext and conversation history variables
    // Note: Langfuse prompt uses VORHERIGE_KONVERSATION (singular), fallback uses VORHERIGE_KONVERSATIONEN (plural)
    const systemPrompt = this.compileTemplate(systemTemplate, {
      Kontext: input.schemaContext,
      VORHERIGE_KONVERSATION: formattedHistory,
      VORHERIGE_KONVERSATIONEN: formattedHistory,
    });

    // Compile user prompt with Frage variable
    let userPrompt = userTemplate
      ? this.compileTemplate(userTemplate, {
          Frage: input.userQuestion,
          VORHERIGE_KONVERSATION: formattedHistory,
          VORHERIGE_KONVERSATIONEN: formattedHistory,
        })
      : `AKTUELLE FRAGE:\n${input.userQuestion}`;
    
    // Check if variable was substituted - if not, always prepend the conversation history
    const historyInSystem = systemPrompt.includes('Keine vorherige Konversation') || systemPrompt.includes('Nutzer:');
    const historyInUser = userPrompt.includes('Keine vorherige Konversation') || userPrompt.includes('Nutzer:');
    
    // If conversation history wasn't included via template substitution, prepend it manually
    if (!historyInSystem && !historyInUser && input.conversationHistory && input.conversationHistory.length > 0) {
      userPrompt = `VORHERIGE KONVERSATION:\n${formattedHistory}\n\n${userPrompt}`;
      console.log(`   ⚠️ History not in template - prepended manually`);
    }
    
    console.log(`   ✓ Prompts compiled (history in system: ${historyInSystem}, in user: ${historyInUser})`);

    // Create trace with input (only user question, not full conversation)
    const trace = langfuseService.createTrace('chat-sql-generation', {
      input: input.userQuestion,
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_fallback: meta.fallbackFile,
      },
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

    try {
      console.log(`   ⏳ Calling LLM for SQL generation...`);
      
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

      console.log(`   ✓ SQL Generation complete:`);
      console.log(`     SQL: ${data.sql ? data.sql.substring(0, 100) + '...' : '<NONE>'}`);
      console.log(`     Confidence: ${data.confidence}`);
      console.log(`     Needs clarification: ${data.needsClarification || '<NONE>'}`);

      // End generation (latency calculated automatically by Langfuse)
      langfuseService.endGeneration(generation, data, usage);

      // End trace with output (only the SQL query, not the full response object)
      langfuseService.endTrace(trace, data.sql);

      // Flush to Langfuse
      await langfuseService.flush();
      console.log(`   ✓ Langfuse trace flushed`);
      console.log(`🔍 [SQL GENERATOR] ✅ Complete\n`);

      return {
        result: data,
        traceId: trace?.id,
        generationId: generation?.id,
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorStack = error instanceof Error ? error.stack : '';
      console.error(`\n❌ [SQL GENERATOR] FAILED`);
      console.error(`   Error: ${errorMessage}`);
      if (errorStack && typeof errorStack === 'string') {
        console.error(`   Stack: ${errorStack.substring(0, 300)}`);
      }
      throw error;
    }
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
    console.log(`\n💬 [CHAT ANSWER FORMATTER] Starting answer formatting...`);
    console.log(`   Question: "${input.userQuestion?.substring(0, 80) ?? '<no question>'}..."`);
    console.log(`   SQL Result rows: ${input.sqlResult?.length ?? 0}`);

    const promptKey = 'chat-answer-formatter';

    // Load prompt template with config
    const { system: systemTemplate, user: userTemplate, config, meta } = await this.loadPromptTemplate(promptKey);
    console.log(`   ✓ Loaded prompt template`);

    // Compile system prompt with German variable names
    const systemPrompt = this.compileTemplate(systemTemplate, {
      FRAGE: input.userQuestion,
      SQL: input.sqlQuery,
      ANTWORT: JSON.stringify(input.sqlResult, null, 2),
      VORHERIGE_KONVERSATION: '', // TODO: Add conversation history if available
      STYLE: input.style || 'Hochdeutsch',
    });
    console.log(`   ✓ System prompt compiled`);
    
    // Use user template or provide the fixed user prompt
    const userPrompt = userTemplate 
      ? this.compileTemplate(userTemplate, {
          FRAGE: input.userQuestion,
          SQL: input.sqlQuery,
          ANTWORT: JSON.stringify(input.sqlResult, null, 2),
          VORHERIGE_KONVERSATION: '',
        })
      : `Generiere eine Antwort für den Chat mit dem Nutzer`;

    try {
      // Create trace with input (only the user question)
      const trace = langfuseService.createTrace('chat-answer-formatting', {
        input: input.userQuestion,
        metadata: {
          prompt_key: promptKey,
          prompt_source: meta.source,
          prompt_name: meta.promptName,
          prompt_label: meta.promptLabel,
          prompt_version: meta.promptVersion,
          prompt_fallback: meta.fallbackFile,
        },
      });
      console.log(`   ✓ Langfuse trace created`);

      // Get model from config (prompt-specific or default)
      const model = promptsConfig.getModelForPrompt(promptKey);

      // Fetch the prompt object from Langfuse to link it to the generation
      const langfusePrompt = await langfuseService.getPrompt(meta.promptName,
        meta.promptVersion && meta.promptVersion !== 'fallback' ? Number(meta.promptVersion) : undefined
      );
      console.log(`   ✓ Langfuse prompt fetched`);

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
      console.log(`   ✓ Generation started (calling LLM...)`);

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
      console.log(`   ✓ Answer formatted successfully`);
      console.log(`   📝 LLM Response:`, JSON.stringify(data, null, 2));

      // End generation (latency calculated automatically by Langfuse)
      langfuseService.endGeneration(generation, data, usage);

      // End trace with output (only the formatted answer)
      langfuseService.endTrace(trace, data.answer);

      // Flush to Langfuse
      await langfuseService.flush();
      console.log(`   ✓ Langfuse trace flushed`);
      console.log(`💬 [CHAT ANSWER FORMATTER] ✅ Complete\n`);
      
      return {
        result: data,
        traceId: trace?.id,
        generationId: generation?.id,
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorStack = error instanceof Error ? error.stack : '';
      console.error(`\n❌ [CHAT ANSWER FORMATTER] FAILED`);
      console.error(`   Error: ${errorMessage}`);
      if (errorStack && typeof errorStack === 'string') {
        console.error(`   Stack: ${errorStack.substring(0, 300)}`);
      }
      throw error;
    }
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

    // Compile system prompt with variables
    const systemPrompt = this.compileTemplate(systemTemplate, {
      schemaContext: input.schemaContext,
      Thema: input.category,
      Schwierigkeitsgrad: input.difficulty,
      Rundenanzahl: String(input.rounds),
      AnzahlMitspieler: String(input.numberOfPlayers),
    });

    // Compile user prompt from template (or construct if template is empty)
    const userPrompt = userTemplate 
      ? this.compileTemplate(userTemplate, {
          category: input.category,
          difficulty: input.difficulty,
          count: String(input.count),
        })
      : `Category: ${input.category}\nDifficulty: ${input.difficulty}\nNumber of Questions: ${input.count}`;

    // Create trace with input (only the prompt)
    const trace = langfuseService.createTrace('quiz-question-generation', {
      input: userPrompt,
      metadata: {
        prompt_key: promptKey,
        prompt_source: meta.source,
        prompt_name: meta.promptName,
        prompt_label: meta.promptLabel,
        prompt_version: meta.promptVersion,
        prompt_fallback: meta.fallbackFile,
      },
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

    // Define JSON Schema for structured output (enforces exact field names)
    const questionSchema = {
      name: 'quiz_questions',
      strict: true,
      schema: {
        type: 'object' as const,
        properties: {
          questions: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                questionText: {
                  type: 'string',
                  description: 'The quiz question text in German',
                },
                sqlQueryNeeded: {
                  type: 'string',
                  description: 'SQL query to validate the answer against the database',
                },
              },
              required: ['questionText', 'sqlQueryNeeded'],
              additionalProperties: false,
            },
            description: 'Array of quiz questions with their SQL queries',
          },
        },
        required: ['questions'],
        additionalProperties: false,
      },
    };

    // Call OpenRouter with JSON Schema for structured output
    const { data: rawData, usage } = await openRouterService.generateJSON<any>(
      userPrompt,
      {
        model: model,
        systemInstruction: systemPrompt,
        temperature: config.llm_config.temperature,
        maxOutputTokens: config.llm_config.max_tokens,
        responseFormat: 'json_schema',
        jsonSchema: questionSchema,
      }
    );

    // Normalize the LLM response to handle German/English field name variations
    const normalizedData = normalizeQuestionGeneratorOutput(rawData);
    console.log(`   📦 DEBUG - Normalized ${normalizedData.questions.length} questions`);

    // End generation (latency calculated automatically by Langfuse)
    langfuseService.endGeneration(generation, normalizedData, usage);

    // End trace with output (only the questions array)
    langfuseService.endTrace(trace, normalizedData.questions);

    // Flush to Langfuse
    await langfuseService.flush();

    return {
      result: normalizedData,
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
    console.log(`🎯 [ANSWER GENERATOR] Starting answer generation...`);
    console.log(`   Question: "${input.question?.substring(0, 80) ?? '<no question>'}..."`);
    console.log(`   SQL Result rows: ${Array.isArray(input.sqlResult) ? input.sqlResult.length : 'N/A'}`);
    
    const promptKey = 'quiz-answer-generator';

    try {
      // Load prompt template with config
      const { system: systemTemplate, user: userTemplate, config, meta } = await this.loadPromptTemplate(promptKey);
      console.log(`   ✓ Loaded prompt template`);

      // Compile system prompt
      const systemPrompt = systemTemplate;
      
      // Compile user prompt from template (or construct if template is empty)
      const userPrompt = userTemplate
        ? this.compileTemplate(userTemplate, {
            question: input.question,
            difficulty: input.difficulty,
            sqlQuery: input.sqlQuery,
            sqlResult: JSON.stringify(input.sqlResult, null, 2),
          })
        : `Question: ${input.question}\nDifficulty: ${input.difficulty}\n\nSQL Query:\n${input.sqlQuery}\n\nSQL Result:\n${JSON.stringify(input.sqlResult, null, 2)}`;

      console.log(`   ✓ User prompt compiled`);

      // Create trace with input (only the question)
      const trace = langfuseService.createTrace('quiz-answer-generation', {
        input: input.question,
        metadata: {
          prompt_key: promptKey,
          prompt_source: meta.source,
          prompt_name: meta.promptName,
          prompt_label: meta.promptLabel,
          prompt_version: meta.promptVersion,
          prompt_fallback: meta.fallbackFile,
        },
      });
      console.log(`   ✓ Langfuse trace created`);

      // Get model from config (prompt-specific or default)
      const model = promptsConfig.getModelForPrompt(promptKey);

      // Fetch the prompt object from Langfuse to link it to the generation
      const langfusePrompt = await langfuseService.getPrompt(meta.promptName,
        meta.promptVersion && meta.promptVersion !== 'fallback' ? Number(meta.promptVersion) : undefined
      );
      console.log(`   ✓ Langfuse prompt fetched`);

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
      console.log(`   ✓ Generation started (calling LLM...)`);

      // Define JSON Schema for structured output (enforces exact field names)
      const answerSchema = {
        name: 'quiz_answer',
        strict: true,
        schema: {
          type: 'object' as const,
          properties: {
            correctAnswer: {
              type: 'string',
              description: 'The correct answer to the quiz question',
            },
            incorrectAnswers: {
              type: 'array',
              items: { type: 'string' },
              description: 'Array of 3 plausible but incorrect answer alternatives',
            },
            explanation: {
              type: 'string',
              description: 'Brief explanation of why the answer is correct',
            },
            evidenceScore: {
              type: 'number',
              description: 'Confidence score from 0 to 1 based on SQL evidence',
            },
          },
          required: ['correctAnswer', 'incorrectAnswers', 'explanation', 'evidenceScore'],
          additionalProperties: false,
        },
      };

      // Call OpenRouter with JSON Schema for structured output
      const { data: rawData, usage } = await openRouterService.generateJSON<any>(
        userPrompt,
        {
          model: model,
          systemInstruction: systemPrompt,
          temperature: config.llm_config.temperature,
          maxOutputTokens: config.llm_config.max_tokens,
          responseFormat: 'json_schema',
          jsonSchema: answerSchema,
        }
      );

      // End generation (latency calculated automatically by Langfuse)
      langfuseService.endGeneration(generation, rawData, usage);
      console.log(`   ✓ Answer generation complete:`);
      console.log(`   📦 DEBUG - Raw LLM response:`, JSON.stringify(rawData, null, 2));

      // Normalize the LLM response to handle German/English field name variations
      const normalizedData = normalizeAnswerGeneratorOutput(rawData);
      
      console.log(`     Correct: "${normalizedData.correctAnswer}"`);
      console.log(`     Wrong options: ${normalizedData.incorrectAnswers.map(a => `"${a}"`).join(', ')}`);
      console.log(`     Evidence score: ${normalizedData.evidenceScore}`);

      // End trace with output (only the correct answer)
      langfuseService.endTrace(trace, normalizedData.correctAnswer);

      // Flush to Langfuse
      await langfuseService.flush();
      console.log(`   ✓ Langfuse trace flushed`);
      console.log(`🎯 [ANSWER GENERATOR] ✅ Complete\n`);

      return {
        result: normalizedData,
        traceId: trace?.id,
        generationId: generation?.id,
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorStack = error instanceof Error ? error.stack : '';
      console.error(`\n❌ [ANSWER GENERATOR] FAILED`);
      console.error(`   Error: ${errorMessage}`);
      if (errorStack && typeof errorStack === 'string') {
        console.error(`   Stack: ${errorStack.substring(0, 300)}`);
      }
      throw error;
    }
  }
}

// Singleton instance
export const promptsService = new PromptsService();
