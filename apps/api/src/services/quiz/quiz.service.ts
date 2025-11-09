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

// DTO for joined quiz_rounds + quiz_questions
type QuizRoundWithQuestion = QuizRound & QuizQuestion;

export class QuizService {
  /**
   * Create a new quiz game
   */
  async createGame(request: QuizGameCreateRequest): Promise<QuizGameResponse> {
    const { topic, difficulty, num_rounds, game_mode, category_id, player_names } = request;

    // 1. Create game in database
    const game = await postgresService.queryOne<QuizGame>(
      `INSERT INTO public.quiz_games (topic, difficulty, num_rounds, game_mode, category_id)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING *`,
      [topic ?? null, difficulty, num_rounds, game_mode ?? 'classic', category_id ?? null]
    );

    if (!game) {
      throw new Error('Failed to create game');
    }

    // 2. Create or get quiz players
    for (const playerName of player_names) {
      await postgresService.query(
        `SELECT get_or_create_quiz_player($1)`,
        [playerName]
      );
    }

    // 3. Generate questions for all rounds
    await this.generateQuestionsForGame(game.game_id, {
      category: category_id ?? 'statistics',
      difficulty,
      numRounds: num_rounds,
    });

    // 4. Return response
    return this.formatGameResponse(game);
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
        player_name,
        playerId?.get_or_create_quiz_player ?? null,
        answer,
        isCorrect,
        time_taken,
        pointsEarned,
      ]
    );

    // 6. Return response
    return {
      is_correct: isCorrect,
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
         qa.player_name,
         SUM(qa.points_earned) as score,
         SUM(CASE WHEN qa.is_correct THEN 1 ELSE 0 END) as correct_answers,
         COUNT(*) as total_questions,
         AVG(qa.time_taken) as average_time
       FROM public.quiz_answers qa
       JOIN public.quiz_rounds qr ON qa.round_id = qr.round_id
       WHERE qr.game_id = $1
       GROUP BY qa.player_name
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
  private async generateQuestionsForGame(
    gameId: string,
    config: { category: string; difficulty: 'easy' | 'medium' | 'hard'; numRounds: number }
  ): Promise<void> {
    // 1. Create job records for tracking progress
    for (let i = 1; i <= config.numRounds; i++) {
      await postgresService.query(
        `INSERT INTO quiz_generation_jobs (game_id, round_number, status)
         VALUES ($1, $2, 'pending')`,
        [gameId, i]
      );
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
    console.log(`🎯 Generating ${questionsToGenerate} questions (${config.numRounds} needed + buffer)...`);
    const questionGeneration = await promptsService.executeQuizQuestionGenerator({
      category: config.category,
      difficulty: config.difficulty,
      previousQuestions,
      count: questionsToGenerate,
      schemaContext: getSchemaContext(),
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
          // Step 1: Update job status - SQL generated
          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'sql_generated', generated_question_text = $1, generated_sql = $2, updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $3 AND round_number = $4`,
            [generatedQuestion.questionText, generatedQuestion.sqlQueryNeeded, gameId, roundNumber]
          );
          console.log(`  Round ${roundNumber}: Generated SQL query`);

          // Step 2: Execute SQL to get correct answer
          const { rows } = await postgresService.executeUserQuery(generatedQuestion.sqlQueryNeeded);
          console.log(`  Round ${roundNumber}: Executed SQL, got ${rows.length} result(s)`);

          // Validate results
          if (rows.length === 0) {
            throw new Error('SQL query returned no results');
          }

          // Step 3: Generate alternative answers based on SQL result
          const answerGeneration = await promptsService.executeQuizAnswerGenerator({
            question: generatedQuestion.questionText,
            sqlQuery: generatedQuestion.sqlQueryNeeded,
            sqlResult: rows,
            difficulty: config.difficulty,
          });

          const { correctAnswer, incorrectAnswers, explanation, evidenceScore } = answerGeneration.result;

          // Step 4: Update job status - answer verified
          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'answer_verified', sql_result = $1, correct_answer = $2,
                 incorrect_answers = $3, explanation = $4, updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $5 AND round_number = $6`,
            [JSON.stringify(rows), correctAnswer, JSON.stringify(incorrectAnswers), explanation, gameId, roundNumber]
          );
          console.log(`  Round ${roundNumber}: Verified answer - "${correctAnswer}"`);

          // Step 5: Save question to database
          const allAnswers = [correctAnswer, ...incorrectAnswers];
          const shuffledAnswers = allAnswers.sort(() => Math.random() - 0.5);

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
              JSON.stringify(shuffledAnswers),
              explanation,
              config.difficulty,
              config.category,
              config.category,
              evidenceScore,
              generatedQuestion.sqlQueryNeeded,
              generatedQuestion.expectedAnswerType,
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
          console.log(`  ✅ Round ${roundNumber}: Complete`);

          questionCreated = true;
          roundNumber++;
        } catch (error) {
          // Handle errors - log and skip this question
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'failed', error_message = $1, updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $2 AND round_number = $3`,
            [errorMessage, gameId, roundNumber]
          );
          console.warn(`  ⚠️  Round ${roundNumber}: Question failed - ${errorMessage}`);
          
          retryCount++;
          if (retryCount >= maxRetries) {
            console.warn(`  ⏭️  Skipping question after ${maxRetries} retries, moving to next question`);
            questionIndex++;
            
            // If we've run out of questions, we need to generate more or fail
            if (questionIndex >= questionGeneration.result.questions.length) {
              throw new Error(`Failed to generate ${config.numRounds} valid questions. Only ${roundNumber - 1} succeeded.`);
            }
          }
        }
      }

      if (questionCreated) {
        questionIndex++;
      }
    }

    // Check if we generated enough questions
    if (roundNumber <= config.numRounds) {
      throw new Error(`Only generated ${roundNumber - 1} questions out of ${config.numRounds} requested`);
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

    return {
      game_id: gameId,
      status: failedJob ? 'failed' : completedCount === jobs.length ? 'completed' : 'generating',
      progress: {
        game_id: gameId,
        total_rounds: jobs.length,
        completed_rounds: completedCount,
        current_round: jobs.find((j) => j.status !== 'round_created' && j.status !== 'failed')?.round_number,
        current_status: jobs.find((j) => j.status !== 'round_created' && j.status !== 'failed')?.status,
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
  private async formatGameResponse(game: QuizGame): Promise<QuizGameResponse> {
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

    return {
      game_id: game.game_id,
      topic: game.topic ?? undefined,
      difficulty: game.difficulty,
      num_rounds: game.num_rounds,
      current_round: game.current_round,
      status: game.status,
      game_mode: game.game_mode ?? 'classic',
      category,
      created_at: game.created_at.toISOString(),
      updated_at: game.updated_at.toISOString(),
    };
  }
}

// Singleton instance
export const quizService = new QuizService();
