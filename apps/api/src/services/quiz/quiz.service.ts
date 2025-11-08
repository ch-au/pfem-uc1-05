import { postgresService } from '../database/postgres.service.js';
import { promptsService } from '../ai/prompts.service.js';
import { getSchemaContext } from '../../config/schema-context.js';
import type {
  QuizGame,
  QuizQuestion,
  QuizRound,
  QuizAnswer,
  QuizGameCreateRequest,
  QuizGameResponse,
  QuizQuestionResponse,
  QuizAnswerRequest,
  QuizAnswerResponse,
  QuizLeaderboardResponse,
} from '@fsv/shared-types';

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
    const round = await postgresService.queryOne<QuizRound & { question: QuizQuestion }>(
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
    const round = await postgresService.queryOne<QuizRound & { question: QuizQuestion }>(
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
   * Generate questions for a game
   */
  private async generateQuestionsForGame(
    gameId: string,
    config: { category: string; difficulty: 'easy' | 'medium' | 'hard'; numRounds: number }
  ): Promise<void> {
    // 1. Get existing questions in this category to avoid duplicates
    const existingQuestions = await postgresService.queryMany<{ question_text: string }>(
      `SELECT question_text FROM public.quiz_questions
       WHERE category_id = (SELECT category_id FROM public.quiz_categories WHERE name = $1)
       ORDER BY times_used ASC
       LIMIT 100`,
      [config.category]
    );

    const previousQuestions = existingQuestions.map((q) => q.question_text);

    // 2. PROMPT 3: Generate questions
    const questionGeneration = await promptsService.executeQuizQuestionGenerator({
      category: config.category,
      difficulty: config.difficulty,
      previousQuestions,
      count: config.numRounds,
      schemaContext: getSchemaContext(),
    });

    // 3. For each generated question, execute SQL and generate answers
    let roundNumber = 1;
    for (const generatedQuestion of questionGeneration.result.questions) {
      // Execute SQL to get data
      const { rows } = await postgresService.executeUserQuery(generatedQuestion.sqlQueryNeeded);

      // PROMPT 4: Generate answers
      const answerGeneration = await promptsService.executeQuizAnswerGenerator({
        question: generatedQuestion.questionText,
        sqlQuery: generatedQuestion.sqlQueryNeeded,
        sqlResult: rows,
        difficulty: config.difficulty,
      });

      const { correctAnswer, incorrectAnswers, explanation, evidenceScore } = answerGeneration.result;

      // Combine correct and incorrect answers, shuffle
      const allAnswers = [correctAnswer, ...incorrectAnswers];
      const shuffledAnswers = allAnswers.sort(() => Math.random() - 0.5);

      // Save question to database
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

      // Create round linking game to question
      await postgresService.query(
        `INSERT INTO public.quiz_rounds (game_id, question_id, round_number)
         VALUES ($1, $2, $3)`,
        [gameId, question.question_id, roundNumber]
      );

      roundNumber++;
    }
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
