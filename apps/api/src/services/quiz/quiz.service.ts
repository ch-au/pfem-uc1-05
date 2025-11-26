import { postgresService } from '../database/postgres.service.js';
import { promptsService } from '../ai/prompts.service.js';
import { getSchemaContext } from '../../config/schema-context.js';
import type {
  QuizGame,
  QuizQuestion,
  QuizRound,
  QuizGenerationJob,
  QuizGameCreateRequest,
  QuizGameResponse,
  QuizQuestionResponse,
  QuizAnswerRequest,
  QuizAnswerResponse,
  QuizLeaderboardResponse,
  QuizGenerationProgressResponse,
} from '@fsv/shared-types';
import { quizJobQueue } from './quiz.job-queue.js';

// DTO for joined quiz_rounds + quiz_questions
type QuizRoundWithQuestion = QuizRound & QuizQuestion;

export class QuizService {
  /**
   * Create a new quiz game
   */
  async createGame(request: QuizGameCreateRequest): Promise<QuizGameResponse> {
    const { topic, difficulty, num_rounds, game_mode, category_id } = request;
    const normalizedPlayers = this.normalizePlayerNames(request.player_names);

    if (!normalizedPlayers || normalizedPlayers.length === 0) {
      throw new Error('At least one player name is required to create a quiz game');
    }

    // 1. Create game in database
    const game = await postgresService.queryOne<QuizGame>(
      `INSERT INTO public.quiz_games (topic, difficulty, num_rounds, game_mode, category_id, player_names)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING *`,
      [topic ?? null, difficulty, num_rounds, game_mode ?? 'classic', category_id ?? null, JSON.stringify(normalizedPlayers)]
    );

    if (!game) {
      throw new Error('Failed to create game');
    }

    // 2. Create or get quiz players
    for (const playerName of normalizedPlayers) {
      await postgresService.query(
        `SELECT get_or_create_quiz_player($1)`,
        [playerName]
      );
    }

    // 3. Generate questions for all rounds
    const generationJob = quizJobQueue.enqueue(() =>
      this.generateQuestionsForGame(game.game_id, {
        category: category_id ?? 'statistics',
        difficulty,
        numRounds: num_rounds,
        numberOfPlayers: normalizedPlayers.length,
      })
    );

    // 4. Return response
    return this.formatGameResponse(game, {
      generation_job_id: generationJob.id,
      generation_status: generationJob.status,
    });
  }

  /**
   * Start a quiz game
   */
  async startGame(gameId: string): Promise<QuizGameResponse> {
    const game = await postgresService.queryOne<QuizGame>(
      `UPDATE public.quiz_games
       SET status = 'in_progress', current_round = 1
       WHERE game_id = $1
       RETURNING *`,
      [gameId]
    );

    if (!game) {
      throw new Error('Game not found');
    }

    return this.formatGameResponse(game);
  }

  /**
   * Get game state
   */
  async getGame(gameId: string): Promise<QuizGameResponse> {
    const game = await postgresService.queryOne<QuizGame>(
      `SELECT * FROM public.quiz_games WHERE game_id = $1`,
      [gameId]
    );

    if (!game) {
      throw new Error('Game not found');
    }

    return this.formatGameResponse(game);
  }

  /**
   * Get current question for game
   */
  async getCurrentQuestion(gameId: string): Promise<QuizQuestionResponse> {
    const game = await this.getGame(gameId);

    if (game.status !== 'in_progress') {
      throw new Error('Game is not in progress');
    }

    // Get question for current round
    const round = await postgresService.queryOne<QuizRoundWithQuestion>(
      `SELECT qr.*, qq.*
       FROM public.quiz_rounds qr
       JOIN public.quiz_questions qq ON qr.question_id = qq.question_id
       WHERE qr.game_id = $1 AND qr.round_number = $2`,
      [gameId, game.current_round]
    );

    if (!round) {
      // Check if questions are still generating
      const generationStatus = await postgresService.queryOne<{ status: string; total: number; completed: number }>(
        `SELECT 
           COALESCE((SELECT status FROM quiz_generation_jobs WHERE game_id = $1 ORDER BY updated_at DESC LIMIT 1), 'pending') as status,
           (SELECT COUNT(*) FROM quiz_generation_jobs WHERE game_id = $1) as total,
           (SELECT COUNT(*) FROM quiz_generation_jobs WHERE game_id = $1 AND status = 'round_created') as completed`,
        [gameId]
      );

      if (generationStatus && generationStatus.total > 0 && generationStatus.completed < generationStatus.total) {
        throw new Error(`Questions are still being generated. Progress: ${generationStatus.completed}/${generationStatus.total} completed`);
      }

      throw new Error('Question not found for current round');
    }

    // Parse alternatives from JSONB
    const alternatives = Array.isArray(round.alternatives)
      ? round.alternatives
      : typeof round.alternatives === 'string'
      ? JSON.parse(round.alternatives)
      : [];

    return {
      question_id: round.question_id,
      question_text: round.question_text,
      alternatives,
      difficulty: round.difficulty,
      category: round.topic ?? undefined,
      hint: round.explanation ?? undefined,
      time_limit_seconds: 30, // Default time limit
    };
  }

  /**
   * Submit an answer
   */
  async submitAnswer(
    gameId: string,
    roundNumber: number,
    request: QuizAnswerRequest
  ): Promise<QuizAnswerResponse> {
    const { player_name, answer, time_taken } = request;
    const cleanedPlayerName = player_name.trim();

    // 1. Get round and question
    const round = await postgresService.queryOne<QuizRoundWithQuestion>(
      `SELECT qr.*, qq.*
       FROM public.quiz_rounds qr
       JOIN public.quiz_questions qq ON qr.question_id = qq.question_id
       WHERE qr.game_id = $1 AND qr.round_number = $2`,
      [gameId, roundNumber]
    );

    if (!round) {
      throw new Error('Round not found');
    }

    // 2. Check if answer is correct
    const isCorrect = answer.trim().toLowerCase() === round.correct_answer.trim().toLowerCase();

    // 3. Calculate points (time-based scoring)
    const maxPoints = 100;
    const timeBonus = Math.max(0, maxPoints - Math.floor(time_taken * 2));
    const pointsEarned = isCorrect ? Math.max(10, timeBonus) : 0;

    // 4. Get or create player
    const playerId = await postgresService.queryOne<{ get_or_create_quiz_player: string }>(
      `SELECT get_or_create_quiz_player($1) as get_or_create_quiz_player`,
      [player_name]
    );

    // 5. Save answer
    await postgresService.query(
      `INSERT INTO public.quiz_answers
       (round_id, player_name, quiz_player_id, answer, is_correct, time_taken, points_earned)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        round.round_id,
        cleanedPlayerName,
        playerId?.get_or_create_quiz_player ?? null,
        answer,
        isCorrect,
        time_taken,
        pointsEarned,
      ]
    );

    // 6. Return response
    return {
      correct: isCorrect,
      correct_answer: round.correct_answer,
      explanation: round.explanation ?? undefined,
      points_earned: pointsEarned,
    };
  }

  /**
   * Advance to next round
   */
  async nextRound(gameId: string): Promise<QuizGameResponse> {
    const game = await postgresService.queryOne<QuizGame>(
      `SELECT * FROM public.quiz_games WHERE game_id = $1`,
      [gameId]
    );

    if (!game) {
      throw new Error('Game not found');
    }

    if (game.current_round >= game.num_rounds) {
      // Game is complete
      await postgresService.query(
        `UPDATE public.quiz_games
         SET status = 'completed', completed_at = CURRENT_TIMESTAMP, current_round = $2
         WHERE game_id = $1`,
        [gameId, game.current_round + 1]
      );

      return this.getGame(gameId);
    }

    // Advance to next round
    const updatedGame = await postgresService.queryOne<QuizGame>(
      `UPDATE public.quiz_games
       SET current_round = current_round + 1
       WHERE game_id = $1
       RETURNING *`,
      [gameId]
    );

    if (!updatedGame) {
      throw new Error('Failed to advance round');
    }

    return this.formatGameResponse(updatedGame);
  }

  /**
   * Get leaderboard for a game
   */
  async getLeaderboard(gameId: string): Promise<QuizLeaderboardResponse> {
    const leaderboard = await postgresService.queryMany<{
      player_name: string;
      score: number;
      correct_answers: number;
      total_questions: number;
      average_time: number;
    }>(
      `SELECT
         MIN(qa.player_name) as player_name,
         SUM(qa.points_earned) as score,
         SUM(CASE WHEN qa.is_correct THEN 1 ELSE 0 END) as correct_answers,
         COUNT(*) as total_questions,
         AVG(qa.time_taken) as average_time
       FROM public.quiz_answers qa
       JOIN public.quiz_rounds qr ON qa.round_id = qr.round_id
       WHERE qr.game_id = $1
       GROUP BY LOWER(TRIM(qa.player_name))
       ORDER BY score DESC`,
      [gameId]
    );

    return {
      game_id: gameId,
      leaderboard: leaderboard.map((row) => ({
        player_name: row.player_name,
        score: Number(row.score),
        correct_answers: Number(row.correct_answers),
        total_questions: Number(row.total_questions),
        average_time: Number(row.average_time),
      })),
    };
  }

  /**
   * Generate questions for a game with progress tracking
   */
  async generateQuestionsForGame(
    gameId: string,
    config: { category: string; difficulty: 'easy' | 'medium' | 'hard'; numRounds: number; numberOfPlayers: number },
    options?: { ensureJobs?: boolean }
  ): Promise<void> {
    const ensureJobs = options?.ensureJobs ?? true;

    // 1. Create job records for tracking progress
    if (ensureJobs) {
      const existingJobs = await postgresService.queryMany<{ round_number: number }>(
        `SELECT round_number FROM quiz_generation_jobs WHERE game_id = $1 ORDER BY round_number ASC`,
        [gameId]
      );

      if (existingJobs.length === 0) {
        for (let i = 1; i <= config.numRounds; i++) {
          await postgresService.query(
            `INSERT INTO quiz_generation_jobs (game_id, round_number, status)
             VALUES ($1, $2, 'pending')`,
            [gameId, i]
          );
        }
      }
    }

    // 2. Get existing questions to avoid duplicates
    const existingQuestions = await postgresService.queryMany<{ question_text: string }>(
      `SELECT question_text FROM public.quiz_questions
       WHERE category_id = (SELECT category_id FROM public.quiz_categories WHERE name = $1)
       ORDER BY times_used ASC LIMIT 100`,
      [config.category]
    );

    const previousQuestions = existingQuestions.map((q) => q.question_text);

    // 3. Generate questions with SQL queries (with buffer for failures)
    const bufferMultiplier = 1.5; // Generate 50% more questions as buffer
    const questionsToGenerate = Math.ceil(config.numRounds * bufferMultiplier);
    console.log(
      `\n${'='.repeat(80)}\n🎯 QUIZ GENERATION START\n${'='.repeat(80)}\nGenerating ${questionsToGenerate} questions (${config.numRounds} needed + buffer)\nCategory: ${config.category} | Difficulty: ${config.difficulty}\nGame ID: ${gameId}\n${'='.repeat(80)}\n`
    );
    const questionGeneration = await promptsService.executeQuizQuestionGenerator({
      category: config.category,
      difficulty: config.difficulty,
      previousQuestions,
      count: questionsToGenerate,
      schemaContext: getSchemaContext(),
      rounds: config.numRounds,
      numberOfPlayers: config.numberOfPlayers,
    });

    // 4. Process each question sequentially with progress tracking
    let roundNumber = 1;
    let questionIndex = 0;
    const maxRetries = 3; // Max retries per question

    while (roundNumber <= config.numRounds && questionIndex < questionGeneration.result.questions.length) {
      const generatedQuestion = questionGeneration.result.questions[questionIndex];
      let retryCount = 0;
      let questionCreated = false;

      while (!questionCreated && retryCount < maxRetries) {
        try {
          console.log(`\n📋 ROUND ${roundNumber}/${config.numRounds} - Processing Question ${questionIndex + 1}/${questionGeneration.result.questions.length}`);
          console.log(`   Question: "${generatedQuestion.questionText.substring(0, 80)}..."`);
          
          // Step 1: Generate SQL query for the question (using chat-sql-generator)
          console.log(`   ⏳ Step 1: Generating SQL Query...`);
          const sqlGeneration = await promptsService.executeChatSQLGenerator({
            userQuestion: generatedQuestion.questionText,
            conversationHistory: [],
            schemaContext: getSchemaContext(),
          });

          const { sql, confidence, needsClarification } = sqlGeneration.result;

          // Check if SQL was successfully generated
          if (needsClarification || !sql) {
            throw new Error(`SQL generation failed: ${needsClarification || 'No SQL query generated'}`);
          }

          console.log(`   ✓ Step 1: SQL Query Generated (confidence: ${confidence})`);
          console.log(`     SQL: ${sql.substring(0, 120)}...`);

          // Update job status - SQL generated
          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'sql_generated', generated_question_text = $1, generated_sql = $2, updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $3 AND round_number = $4`,
            [generatedQuestion.questionText, sql, gameId, roundNumber]
          );

          // Step 2: Execute SQL to get correct answer (with field metadata)
          console.log(`   ⏳ Step 2: Executing SQL Query...`);
          const { rows, fields } = await postgresService.executeUserQuery(sql);
          console.log(`   ✓ Step 2: SQL Executed Successfully - Got ${rows.length} result row(s)`);
          console.log(`     First result: ${JSON.stringify(rows[0]).substring(0, 100)}...`);

          // Validate results
          if (rows.length === 0) {
            throw new Error('SQL query returned no results');
          }

          // Infer answer type from SQL result metadata (first column type)
          let answerType: 'number' | 'string' | 'date' | 'list' = 'string'; // default fallback
          if (fields && fields.length > 0) {
            const firstFieldType = fields[0].dataTypeID;
            // PostgreSQL data type IDs (common ones)
            // 23 = int4, 20 = int8, 21 = int2, 700 = float4, 701 = float8, 1700 = numeric
            // 1082 = date, 1114 = timestamp, 1184 = timestamptz
            // 25 = text, 1043 = varchar, 1042 = char
            // 1007 = _int4 (int array), 1009 = _text (text array)
            if ([23, 20, 21, 700, 701, 1700].includes(firstFieldType)) {
              answerType = 'number';
            } else if ([1082, 1114, 1184].includes(firstFieldType)) {
              answerType = 'date';
            } else if ([1007, 1009, 1016, 1231].includes(firstFieldType)) {
              answerType = 'list';
            }
          }
          console.log(`   📊 Inferred answer type from SQL: ${answerType}`);

          // Step 3: Generate alternative answers based on SQL result
          console.log(`   ⏳ Step 3: Generating Answer Alternatives...`);
          const answerGeneration = await promptsService.executeQuizAnswerGenerator({
            question: generatedQuestion.questionText,
            sqlQuery: sql,
            sqlResult: rows,
            difficulty: config.difficulty,
          });

          const { correctAnswer, incorrectAnswers, explanation, evidenceScore } = answerGeneration.result;
          console.log(`   ✓ Step 3: Answer Generated`);
          console.log(`     Correct: "${correctAnswer}"`);
          console.log(`     Wrong: ${incorrectAnswers.map(a => `"${a}"`).join(', ')}`);

          // Step 4: Update job status - answer verified
          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'answer_verified', sql_result = $1, correct_answer = $2,
                 incorrect_answers = $3, explanation = $4, updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $5 AND round_number = $6`,
            [JSON.stringify(rows), correctAnswer, JSON.stringify(incorrectAnswers), explanation, gameId, roundNumber]
          );
          console.log(`   ✓ Step 4: Saved to Database`);

          // Step 5: Save question to database
          const allAnswers = [correctAnswer, ...incorrectAnswers];
          // Keep answer order stable; no shuffling on the server
          const stableAnswers = allAnswers;

          const question = await postgresService.queryOne<QuizQuestion>(
            `INSERT INTO public.quiz_questions
             (question_text, correct_answer, alternatives, explanation, difficulty, topic,
              category_id, evidence_score, sql_query, answer_type, langfuse_trace_id)
             VALUES ($1, $2, $3, $4, $5, $6,
                     (SELECT category_id FROM public.quiz_categories WHERE name = $7),
                     $8, $9, $10, $11)
             RETURNING *`,
            [
              generatedQuestion.questionText,
              correctAnswer,
              JSON.stringify(stableAnswers),
              explanation,
              config.difficulty,
              config.category,
              config.category,
              evidenceScore,
              sql,
              answerType,
              answerGeneration.traceId ?? null,
            ]
          );

          if (!question) {
            throw new Error('Failed to create question');
          }

          // Step 6: Create round and mark job as complete
          await postgresService.query(
            `INSERT INTO public.quiz_rounds (game_id, question_id, round_number)
             VALUES ($1, $2, $3)`,
            [gameId, question.question_id, roundNumber]
          );

          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'round_created', updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $1 AND round_number = $2`,
            [gameId, roundNumber]
          );
          console.log(`   ✓ Step 5: Question Saved to Database`);
          console.log(`\n✅ ROUND ${roundNumber} COMPLETE\n`);

          questionCreated = true;
          roundNumber++;
        } catch (error) {
          // Handle errors - log and skip this question
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          const errorStack = error instanceof Error ? error.stack : '';
          
          console.error(`\n❌ ROUND ${roundNumber} ERROR (Attempt ${retryCount + 1}/${maxRetries})`);
          console.error(`   Error: ${errorMessage}`);
          if (errorStack) {
            console.error(`   Stack: ${errorStack.substring(0, 200)}`);
          }
          
          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'failed', error_message = $1, updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $2 AND round_number = $3`,
            [errorMessage, gameId, roundNumber]
          );
          
          retryCount++;
          if (retryCount >= maxRetries) {
            console.warn(`   ⏭️  Skipping question after ${maxRetries} retries, moving to next question\n`);
            questionIndex++;
            
            // If we've run out of questions, we need to generate more or fail
            if (questionIndex >= questionGeneration.result.questions.length) {
              throw new Error(`Failed to generate ${config.numRounds} valid questions. Only ${roundNumber - 1} succeeded.`);
            }
          } else {
            console.log(`   🔄 Retrying...\n`);
          }
        }
      }

      if (questionCreated) {
        questionIndex++;
      }
    }

    // Check if we generated enough questions
    const generatedCount = roundNumber - 1;
    const minimumRequired = Math.max(1, Math.floor(config.numRounds * 0.6)); // Accept at least 60% success
    
    if (generatedCount < minimumRequired) {
      throw new Error(`Only generated ${generatedCount} questions out of ${config.numRounds} requested (minimum ${minimumRequired} required)`);
    }
    
    // If we generated fewer than requested but still enough, update the game's num_rounds
    if (generatedCount < config.numRounds) {
      console.warn(`⚠️  Generated ${generatedCount}/${config.numRounds} questions. Adjusting game to use available questions.`);
      await postgresService.query(
        `UPDATE public.quiz_games SET num_rounds = $1 WHERE game_id = $2`,
        [generatedCount, gameId]
      );
    }
  }

  /**
   * Get quiz generation progress
   */
  async getGenerationProgress(gameId: string): Promise<QuizGenerationProgressResponse> {
    const jobs = await postgresService.queryMany<QuizGenerationJob>(
      `SELECT * FROM quiz_generation_jobs
       WHERE game_id = $1
       ORDER BY round_number ASC`,
      [gameId]
    );

    if (jobs.length === 0) {
      throw new Error('No generation jobs found for this game');
    }

    const completedCount = jobs.filter((j) => j.status === 'round_created').length;
    const failedJob = jobs.find((j) => j.status === 'failed');
    const active = jobs.find((j) => j.status !== 'round_created' && j.status !== 'failed');

    return {
      game_id: gameId,
      status: failedJob ? 'failed' : completedCount === jobs.length ? 'completed' : 'generating',
      progress: {
        game_id: gameId,
        total_rounds: jobs.length,
        completed_rounds: completedCount,
        current_round: active?.round_number,
        current_status: active?.status,
        error_message: failedJob?.error_message,
        rounds: jobs.map((j) => ({
          round_number: j.round_number,
          status: j.status,
          question_preview: j.generated_question_text?.substring(0, 100),
          error_message: j.error_message,
        })),
      },
    };
  }

  /**
   * Format game response
   */
  private async formatGameResponse(
    game: QuizGame,
    generationMeta?: { generation_job_id: string; generation_status: 'queued' | 'running' | 'succeeded' | 'failed' }
  ): Promise<QuizGameResponse> {
    let category = undefined;
    if (game.category_id) {
      const cat = await postgresService.queryOne<{ category_id: string; name: string; display_name_de: string }>(
        `SELECT category_id, name, display_name_de FROM public.quiz_categories WHERE category_id = $1`,
        [game.category_id]
      );
      if (cat) {
        category = {
          category_id: cat.category_id,
          name: cat.name,
          display_name_de: cat.display_name_de,
        };
      }
    }

    const players = Array.isArray(game.player_names)
      ? this.normalizePlayerNames(game.player_names)
      : typeof game.player_names === 'string'
      ? this.normalizePlayerNames(JSON.parse(game.player_names))
      : [];

    return {
      game_id: game.game_id,
      topic: game.topic ?? undefined,
      difficulty: game.difficulty,
      num_rounds: game.num_rounds,
      current_round: game.current_round,
      status: game.status,
      game_mode: game.game_mode ?? 'classic',
      category,
      players,
      created_at: game.created_at.toISOString(),
      updated_at: game.updated_at.toISOString(),
      ...(generationMeta ? generationMeta : {}),
    };
  }

  /**
   * Get game history (all games or filtered by status)
   */
  async getGameHistory(options?: {
    status?: 'pending' | 'in_progress' | 'completed' | 'abandoned';
    limit?: number;
    offset?: number;
  }): Promise<{ games: QuizGameResponse[]; total: number }> {
    const { status, limit = 50, offset = 0 } = options ?? {};

    // Build query
    let whereClause = '';
    const params: any[] = [];

    if (status) {
      whereClause = 'WHERE status = $1';
      params.push(status);
    }

    // Get total count
    const countResult = await postgresService.queryOne<{ count: string }>(
      `SELECT COUNT(*) as count FROM public.quiz_games ${whereClause}`,
      params
    );
    const total = parseInt(countResult?.count ?? '0');

    // Get games with pagination
    const games = await postgresService.queryMany<QuizGame>(
      `SELECT * FROM public.quiz_games
       ${whereClause}
       ORDER BY created_at DESC
       LIMIT $${params.length + 1} OFFSET $${params.length + 2}`,
      [...params, limit, offset]
    );

    // Convert to response format
    const gameResponses: QuizGameResponse[] = [];
    for (const game of games) {
      const gameResponse = await this.formatGameResponse(game);
      gameResponses.push(gameResponse);
    }

    return { games: gameResponses, total };
  }

  /**
   * Get completed games only
   */
  async getCompletedGames(limit: number = 50, offset: number = 0): Promise<{ games: QuizGameResponse[]; total: number }> {
    return this.getGameHistory({ status: 'completed', limit, offset });
  }

  /**
   * Global leaderboard (aggregate across all games)
   */
  async getGlobalLeaderboard(limit: number = 20): Promise<QuizLeaderboardResponse['leaderboard']> {
    const rows = await postgresService.queryMany<{
      player_name: string;
      score: number;
      correct_answers: number;
      total_questions: number;
      average_time: number;
    }>(
      `SELECT
         MIN(qa.player_name) as player_name,
         SUM(qa.points_earned) as score,
         SUM(CASE WHEN qa.is_correct THEN 1 ELSE 0 END) as correct_answers,
         COUNT(*) as total_questions,
         AVG(qa.time_taken) as average_time
       FROM public.quiz_answers qa
       GROUP BY LOWER(TRIM(qa.player_name))
       ORDER BY score DESC
       LIMIT $1`,
      [limit]
    );

    return rows.map((row) => ({
      player_name: row.player_name,
      score: Number(row.score),
      correct_answers: Number(row.correct_answers),
      total_questions: Number(row.total_questions),
      average_time: Number(row.average_time),
    }));
  }

  /**
   * Normalize and deduplicate player names (trim, case-insensitive)
   */
  private normalizePlayerNames(names: string[] | null | undefined): string[] {
    if (!names) return [];
    const seen = new Set<string>();
    const result: string[] = [];

    for (const raw of names) {
      if (!raw) continue;
      const trimmed = raw.trim();
      if (!trimmed) continue;
      const key = trimmed.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      result.push(trimmed);
    }

    return result;
  }
}

// Singleton instance
export const quizService = new QuizService();
