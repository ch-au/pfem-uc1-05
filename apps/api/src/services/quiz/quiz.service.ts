import { postgresService } from '../database/postgres.service.js';
import { promptsService } from '../ai/prompts.service.js';
import { getSchemaContext } from '../../config/schema-context.js';
import { quizLogger, type QuizLogContext } from './quiz-logger.js';
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
  KnowledgeBaseOutput,
  KnowledgeBaseResult,
} from '@fsv/shared-types';
import { quizJobQueue } from './quiz.job-queue.js';

// DTO for joined quiz_rounds + quiz_questions
type QuizRoundWithQuestion = QuizRound & QuizQuestion;

// Helper to map legacy database statuses to new simplified statuses
type SimplifiedJobStatus = 'pending' | 'generating_alternatives' | 'round_created' | 'failed';
function mapJobStatus(dbStatus: string): SimplifiedJobStatus {
  switch (dbStatus) {
    case 'sql_generated':
    case 'answer_verified':
      return 'generating_alternatives'; // Map legacy in-progress statuses
    case 'round_created':
      return 'round_created';
    case 'failed':
      return 'failed';
    case 'generating_alternatives':
      return 'generating_alternatives';
    default:
      return 'pending';
  }
}

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
        category: topic ?? category_id ?? 'statistics',
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
    // First check if game exists
    const existingGame = await postgresService.queryOne<QuizGame>(
      `SELECT * FROM public.quiz_games WHERE game_id = $1`,
      [gameId]
    );

    if (!existingGame) {
      throw new Error('Game not found');
    }

    // Check if at least round 1 exists before starting
    const round1Exists = await postgresService.queryOne<{ count: number }>(
      `SELECT COUNT(*) as count FROM public.quiz_rounds WHERE game_id = $1 AND round_number = 1`,
      [gameId]
    );

    if (!round1Exists || round1Exists.count === 0) {
      // Check generation status for better error message
      const genStatus = await postgresService.queryOne<{ total: number; completed: number; status: string }>(
        `SELECT 
           COUNT(*) as total,
           SUM(CASE WHEN status = 'round_created' THEN 1 ELSE 0 END) as completed,
           COALESCE(MAX(status), 'pending') as status
         FROM quiz_generation_jobs WHERE game_id = $1`,
        [gameId]
      );

      if (genStatus && genStatus.total > 0 && genStatus.completed < genStatus.total) {
        throw new Error(`Cannot start game: Questions are still being generated (${genStatus.completed}/${genStatus.total} completed)`);
      }
      throw new Error('Cannot start game: No questions have been generated yet');
    }

    const game = await postgresService.queryOne<QuizGame>(
      `UPDATE public.quiz_games
       SET status = 'in_progress', current_round = 1
       WHERE game_id = $1
       RETURNING *`,
      [gameId]
    );

    if (!game) {
      throw new Error('Failed to start game');
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

    // 2. Check if player has already answered this round
    const existingAnswer = await postgresService.queryOne<{
      is_correct: boolean;
      points_earned: number;
    }>(
      `SELECT is_correct, points_earned FROM public.quiz_answers
       WHERE round_id = $1 AND player_name = $2`,
      [round.round_id, cleanedPlayerName]
    );

    if (existingAnswer) {
      // Player has already answered - return their existing result
      return {
        correct: existingAnswer.is_correct,
        correct_answer: round.correct_answer,
        explanation: round.explanation ?? undefined,
        points_earned: existingAnswer.points_earned,
      };
    }

    // 3. Check if answer is correct
    const isCorrect = answer.trim().toLowerCase() === round.correct_answer.trim().toLowerCase();

    // 4. Calculate points (time-based scoring)
    const maxPoints = 100;
    const timeBonus = Math.max(0, maxPoints - Math.floor(time_taken * 2));
    const pointsEarned = isCorrect ? Math.max(10, timeBonus) : 0;

    // 5. Get or create player
    const playerId = await postgresService.queryOne<{ get_or_create_quiz_player: string }>(
      `SELECT get_or_create_quiz_player($1) as get_or_create_quiz_player`,
      [player_name]
    );

    // 6. Save answer
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

    // 7. Return response
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

    // Check how many rounds actually exist (not just num_rounds target)
    const roundsCount = await postgresService.queryOne<{ count: number; max_round: number }>(
      `SELECT COUNT(*) as count, COALESCE(MAX(round_number), 0) as max_round 
       FROM public.quiz_rounds WHERE game_id = $1`,
      [gameId]
    );

    const actualRoundsAvailable = roundsCount?.max_round ?? 0;

    // Check if we've reached the end of available rounds
    if (game.current_round >= actualRoundsAvailable) {
      // Game is complete (either finished all available rounds or reached target)
      await postgresService.query(
        `UPDATE public.quiz_games
         SET status = 'completed', completed_at = CURRENT_TIMESTAMP
         WHERE game_id = $1`,
        [gameId]
      );

      return this.getGame(gameId);
    }

    const nextRoundNumber = game.current_round + 1;

    // Verify next round actually exists before advancing
    const nextRoundExists = await postgresService.queryOne<{ count: number }>(
      `SELECT COUNT(*) as count FROM public.quiz_rounds WHERE game_id = $1 AND round_number = $2`,
      [gameId, nextRoundNumber]
    );

    if (!nextRoundExists || nextRoundExists.count === 0) {
      // Check if more questions are being generated
      const genStatus = await postgresService.queryOne<{ total: number; completed: number }>(
        `SELECT 
           COUNT(*) as total,
           SUM(CASE WHEN status = 'round_created' THEN 1 ELSE 0 END) as completed
         FROM quiz_generation_jobs WHERE game_id = $1`,
        [gameId]
      );

      if (genStatus && genStatus.total > 0 && genStatus.completed < genStatus.total) {
        throw new Error(`Cannot advance: Round ${nextRoundNumber} is still being generated (${genStatus.completed}/${genStatus.total} completed)`);
      }

      // No more rounds available - complete the game
      await postgresService.query(
        `UPDATE public.quiz_games
         SET status = 'completed', completed_at = CURRENT_TIMESTAMP
         WHERE game_id = $1`,
        [gameId]
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
   * Execute Knowledge Base SQL queries and collect results
   * Returns results array and formatted KNOWLEDGE_BASE string for Quiz_Fragen prompt
   */
  async executeKnowledgeBaseQueries(
    kbOutput: KnowledgeBaseOutput
  ): Promise<{ results: KnowledgeBaseResult[]; formattedKnowledgeBase: string }> {
    console.log(`\n📊 [KB EXECUTION] Executing ${kbOutput.queries.length} SQL queries...`);
    
    const results: KnowledgeBaseResult[] = [];
    const formattedParts: string[] = [];

    for (let i = 0; i < kbOutput.queries.length; i++) {
      const query = kbOutput.queries[i];
      console.log(`   Query ${i + 1}/${kbOutput.queries.length}: ${query.sql_query.substring(0, 60)}...`);

      try {
        const { rows } = await postgresService.executeUserQuery(query.sql_query);
        console.log(`   ✓ Got ${rows.length} results`);

        results.push({
          sql_query: query.sql_query,
          reason: query.reason,
          result: rows,
        });

        formattedParts.push(
          `=== Abfrage ${i + 1} ===\n` +
          `Frage-Hinweis: ${query.reason}\n` +
          `SQL: ${query.sql_query}\n` +
          `Ergebnis: ${JSON.stringify(rows, null, 2)}`
        );
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        console.warn(`   ⚠️ Query ${i + 1} failed: ${errorMsg.substring(0, 100)}`);
        results.push({
          sql_query: query.sql_query,
          reason: query.reason,
          result: [],
        });
        formattedParts.push(
          `=== Abfrage ${i + 1} ===\n` +
          `Frage-Hinweis: ${query.reason}\n` +
          `SQL: ${query.sql_query}\n` +
          `Ergebnis: FEHLER - ${errorMsg.substring(0, 200)}`
        );
      }
    }

    const formattedKnowledgeBase = formattedParts.join('\n\n');
    const successfulQueries = results.filter(r => r.result.length > 0).length;
    console.log(`📊 [KB EXECUTION] ✅ Complete: ${successfulQueries}/${kbOutput.queries.length} successful\n`);

    return { results, formattedKnowledgeBase };
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

    // 3. Generate knowledge base with SQL queries for the topic
    const logCtx: QuizLogContext = { gameId };
    const schemaContext = getSchemaContext();
    
    // Calculate number of KB queries based on rounds (more queries = more facts for questions)
    const kbQueriesCount = Math.max(5, Math.ceil(config.numRounds * 1.5));
    
    quizLogger.info(`🎯 QUIZ GENERATION START`, logCtx, {
      numRounds: config.numRounds,
      category: config.category,
      difficulty: config.difficulty,
      kbQueriesCount,
    });
    
    const generationStart = Date.now();
    
    // Step 1: Generate Knowledge Base SQL queries
    console.log(`\n📚 Step 1: Generating Knowledge Base for topic "${config.category}"...`);
    const kbGeneration = await promptsService.executeKnowledgeBaseGenerator({
      thema: config.category,
      schwierigkeitsgrad: config.difficulty,
      anzahlAbfragen: kbQueriesCount,
      schemaContext,
    });
    
    // Check if the topic was rejected at knowledge base level
    if (kbGeneration.result?.rejection_reason) {
      const rejectionReason = kbGeneration.result.rejection_reason;
      console.log(`🚫 Quiz topic "${config.category}" was rejected at KB level: ${rejectionReason}`);
      
      // Mark game as abandoned so it won't be re-queued
      await postgresService.query(
        `UPDATE quiz_games SET status = 'abandoned' WHERE game_id = $1`,
        [gameId]
      );
      
      // Mark all jobs as failed with rejection reason
      await postgresService.query(
        `UPDATE quiz_generation_jobs 
         SET status = 'failed', error_message = $1, updated_at = CURRENT_TIMESTAMP
         WHERE game_id = $2`,
        [`REJECTED: ${rejectionReason}`, gameId]
      );
      
      // Throw a special error that the API layer can identify
      const error = new Error(rejectionReason);
      (error as any).code = 'TOPIC_REJECTED';
      throw error;
    }
    
    // Step 2: Execute KB SQL queries and format results
    console.log(`\n📊 Step 2: Executing Knowledge Base SQL queries...`);
    const { formattedKnowledgeBase } = await this.executeKnowledgeBaseQueries(kbGeneration.result);
    
    // 4. Generate questions using the knowledge base
    const bufferMultiplier = 2.0; // Reduced buffer since KB provides verified facts
    const questionsToGenerate = Math.max(10, Math.ceil(config.numRounds * bufferMultiplier));
    
    console.log(`\n❓ Step 3: Generating ${questionsToGenerate} questions from Knowledge Base...`);
    const questionGeneration = await promptsService.executeQuizQuestionGenerator({
      category: config.category,
      difficulty: config.difficulty,
      previousQuestions,
      count: questionsToGenerate,
      schemaContext,
      rounds: config.numRounds,
      numberOfPlayers: config.numberOfPlayers,
      knowledgeBase: formattedKnowledgeBase,
    });

    // Check if the topic was rejected (inappropriate content)
    if (questionGeneration.result?.rejected) {
      const rejectionReason = questionGeneration.result.rejection_reason ?? 'Dieses Thema kann nicht verarbeitet werden.';
      console.log(`🚫 Quiz topic "${config.category}" was rejected: ${rejectionReason}`);
      
      // Mark game as abandoned so it won't be re-queued
      await postgresService.query(
        `UPDATE quiz_games SET status = 'abandoned' WHERE game_id = $1`,
        [gameId]
      );
      
      // Mark all jobs as failed with rejection reason
      await postgresService.query(
        `UPDATE quiz_generation_jobs 
         SET status = 'failed', error_message = $1, updated_at = CURRENT_TIMESTAMP
         WHERE game_id = $2`,
        [`REJECTED: ${rejectionReason}`, gameId]
      );
      
      // Throw a special error that the API layer can identify
      const error = new Error(rejectionReason);
      (error as any).code = 'TOPIC_REJECTED';
      throw error;
    }

    // Validate that we received a valid questions array
    const questions = questionGeneration.result?.questions;
    if (!questions || !Array.isArray(questions) || questions.length === 0) {
      console.error(`❌ Question generation failed: received invalid or empty questions array`);
      console.error(`   Raw result: ${JSON.stringify(questionGeneration.result)?.substring(0, 500) ?? 'undefined'}`);
      throw new Error('Question generation failed: LLM returned invalid or empty questions array');
    }

    console.log(`✅ Received ${questions.length} questions from LLM`);

    // 4. Process each question sequentially with progress tracking
    let roundNumber = 1;
    let questionIndex = 0;
    const maxRetries = 2; // Reduced retries since KB provides validated facts

    while (roundNumber <= config.numRounds && questionIndex < questions.length) {
      const generatedQuestion = questions[questionIndex];
      let retryCount = 0;
      let questionCreated = false;

      // Validate that the generated question has valid questionText before processing
      if (!generatedQuestion || !generatedQuestion.questionText || typeof generatedQuestion.questionText !== 'string') {
        console.warn(`\n⚠️  Skipping invalid question at index ${questionIndex}: missing or invalid questionText`);
        console.warn(`   Raw question data: ${JSON.stringify(generatedQuestion)?.substring(0, 200) ?? 'undefined'}`);
        questionIndex++;
        continue;
      }

      while (!questionCreated && retryCount < maxRetries) {
        try {
          console.log(`\n📋 ROUND ${roundNumber}/${config.numRounds} - Processing Question ${questionIndex + 1}/${questions.length}`);
          console.log(`   Question: "${generatedQuestion.questionText.substring(0, 80)}..."`);
          console.log(`   Correct Answer (from KB): "${generatedQuestion.correct_answer}"`);
          
          // Validate correct_answer from Knowledge Base
          if (!generatedQuestion.correct_answer || typeof generatedQuestion.correct_answer !== 'string') {
            console.warn(`   ⚠️ Question missing correct_answer - skipping to next question`);
            questionIndex++;
            break;
          }

          // Update job status - generating alternatives
          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'generating_alternatives', generated_question_text = $1, correct_answer = $2, updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $3 AND round_number = $4`,
            [generatedQuestion.questionText, generatedQuestion.correct_answer, gameId, roundNumber]
          );

          // Step 1: Generate alternative answers using correct_answer from Knowledge Base
          console.log(`   ⏳ Step 1: Generating Answer Alternatives...`);
          const answerGeneration = await promptsService.executeQuizAnswerGenerator({
            question: generatedQuestion.questionText,
            correctAnswer: generatedQuestion.correct_answer,
            difficulty: config.difficulty,
            category: generatedQuestion.category ?? config.category,
            knowledgeBaseContext: formattedKnowledgeBase,
          });

          const { correctAnswer, incorrectAnswers, explanation, evidenceScore } = answerGeneration.result;
          console.log(`   ✓ Step 1: Alternatives Generated`);
          console.log(`     Correct: "${correctAnswer}"`);
          console.log(`     Wrong: ${incorrectAnswers.map(a => `"${a}"`).join(', ')}`);

          // Step 2: Save question to database
          const allAnswers = [correctAnswer, ...incorrectAnswers];
          // Fisher-Yates shuffle for proper randomization
          const shuffledAnswers = [...allAnswers];
          for (let i = shuffledAnswers.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffledAnswers[i], shuffledAnswers[j]] = [shuffledAnswers[j], shuffledAnswers[i]];
          }

          // Infer answer type from correct answer format
          let answerType: 'number' | 'string' | 'date' | 'list' = 'string';
          if (/^\d+$/.test(correctAnswer)) {
            answerType = 'number';
          } else if (/^\d{4}(-\d{2}(-\d{2})?)?$/.test(correctAnswer) || /^\d{1,2}\.\d{1,2}\.\d{4}$/.test(correctAnswer)) {
            answerType = 'date';
          }

          const question = await postgresService.queryOne<QuizQuestion>(
            `INSERT INTO public.quiz_questions
             (question_text, correct_answer, alternatives, explanation, difficulty, topic,
              category_id, evidence_score, answer_type, langfuse_trace_id)
             VALUES ($1, $2, $3, $4, $5, $6,
                     (SELECT category_id FROM public.quiz_categories WHERE name = $7),
                     $8, $9, $10)
             RETURNING *`,
            [
              generatedQuestion.questionText,
              correctAnswer,
              JSON.stringify(shuffledAnswers),
              explanation,
              generatedQuestion.difficulty ?? config.difficulty,
              generatedQuestion.category ?? config.category,
              generatedQuestion.category ?? config.category,
              evidenceScore,
              answerType,
              answerGeneration.traceId ?? null,
            ]
          );

          if (!question) {
            throw new Error('Failed to create question');
          }
          console.log(`   ✓ Step 2: Question Saved to Database`);

          // Step 3: Create round and mark job as complete
          const existingRound = await postgresService.queryOne<{ count: string }>(
            `SELECT COUNT(*) as count FROM public.quiz_rounds WHERE game_id = $1 AND round_number = $2`,
            [gameId, roundNumber]
          );
          
          const roundCount = parseInt(existingRound?.count ?? '0', 10);
          
          if (roundCount === 0) {
            const insertedRound = await postgresService.queryOne<{ round_id: string }>(
              `INSERT INTO public.quiz_rounds (game_id, question_id, round_number)
               VALUES ($1, $2, $3)
               RETURNING round_id`,
              [gameId, question.question_id, roundNumber]
            );
            if (!insertedRound) {
              throw new Error(`Failed to create round ${roundNumber}`);
            }
            console.log(`   ✓ Round ${roundNumber} created with ID: ${insertedRound.round_id}`);
          } else {
            // Update existing round with new question (from retry/re-generation)
            await postgresService.query(
              `UPDATE public.quiz_rounds SET question_id = $1 WHERE game_id = $2 AND round_number = $3`,
              [question.question_id, gameId, roundNumber]
            );
            console.log(`   ⏩ Round ${roundNumber} updated with new question`);
          }

          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'round_created', incorrect_answers = $1, explanation = $2, updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $3 AND round_number = $4`,
            [JSON.stringify(incorrectAnswers), explanation, gameId, roundNumber]
          );
          console.log(`   ✓ Step 3: Round Created`);
          console.log(`\n✅ ROUND ${roundNumber} COMPLETE\n`);

          questionCreated = true;
          roundNumber++;
        } catch (error) {
          const err = error instanceof Error ? error : new Error('Unknown error');
          const logCtx: QuizLogContext = { gameId, roundNumber, stage: 'question_generation' };
          
          // Categorize error for retry logic
          const { code: errorCode, recoverable } = quizLogger.categorizeError(err);
          retryCount++;
          
          console.error(`\n❌ ROUND ${roundNumber} FAILED (attempt ${retryCount}/${maxRetries})`);
          console.error(`   Error: ${err.message}`);
          
          quizLogger.stageFailed(`Round ${roundNumber} (attempt ${retryCount}/${maxRetries})`, logCtx, err, errorCode);
          
          // Update job with error info
          await postgresService.query(
            `UPDATE quiz_generation_jobs
             SET status = 'failed', 
                 error_message = $1, 
                 error_code = $2, 
                 retry_count = $3,
                 updated_at = CURRENT_TIMESTAMP
             WHERE game_id = $4 AND round_number = $5`,
            [err.message, errorCode, retryCount, gameId, roundNumber]
          );
          
          // For unrecoverable errors or max retries, skip to next question
          if (!recoverable || retryCount >= maxRetries) {
            const reason = !recoverable ? `Unrecoverable error (${errorCode})` : `Max retries (${maxRetries}) reached`;
            quizLogger.warn(`${reason} - skipping to next question`, logCtx);
            questionIndex++;
            if (questionIndex >= questions.length) {
              quizLogger.warn(`No more questions available. Generated ${roundNumber - 1}/${config.numRounds}`, logCtx);
              break;
            }
            break;
          }
          
          quizLogger.info(`Retrying (${retryCount}/${maxRetries})...`, logCtx);
        }
      }

      if (questionCreated) {
        questionIndex++;
      }
    }

    // Check if we generated enough questions
    const generatedCount = roundNumber - 1;
    // Accept even 1 successful question - the LLM often generates questions about events that don't exist in the database
    const minimumRequired = 1;
    
    if (generatedCount < minimumRequired) {
      throw new Error(`Quiz generation failed: No valid questions could be created. The AI generated questions about events that don't exist in our historical database. Please try a different topic.`);
    }
    
    // If we generated fewer than requested but still enough, update the game's num_rounds
    if (generatedCount < config.numRounds) {
      quizLogger.warn(`Generated ${generatedCount}/${config.numRounds} questions. Adjusting game.`, logCtx);
      await postgresService.query(
        `UPDATE public.quiz_games SET num_rounds = $1 WHERE game_id = $2`,
        [generatedCount, gameId]
      );
    }
    
    const totalDuration = Date.now() - generationStart;
    quizLogger.info(`✅ QUIZ GENERATION COMPLETE`, logCtx, {
      generatedCount,
      requestedCount: config.numRounds,
      duration_ms: totalDuration,
      avgPerQuestion_ms: Math.round(totalDuration / generatedCount),
    });
  }

  /**
   * Get quiz generation progress
   */
  async getGenerationProgress(gameId: string): Promise<QuizGenerationProgressResponse> {
    // Check game status first
    const game = await postgresService.queryOne<{ status: string; num_rounds: number }>(
      `SELECT status, num_rounds FROM public.quiz_games WHERE game_id = $1`,
      [gameId]
    );

    if (!game) {
      throw new Error('Game not found');
    }

    const jobs = await postgresService.queryMany<QuizGenerationJob>(
      `SELECT * FROM quiz_generation_jobs
       WHERE game_id = $1
       ORDER BY round_number ASC`,
      [gameId]
    );

    // If no jobs exist, return based on game status
    if (jobs.length === 0) {
      // Game exists but no jobs - could be completed/abandoned/in_progress
      const status = game.status === 'in_progress' || game.status === 'completed' 
        ? 'completed' 
        : game.status === 'abandoned' 
          ? 'failed' 
          : 'generating';
      
      return {
        game_id: gameId,
        status,
        progress: {
          game_id: gameId,
          total_rounds: game.num_rounds,
          completed_rounds: game.status === 'in_progress' || game.status === 'completed' ? game.num_rounds : 0,
          current_round: undefined,
          current_status: undefined,
          error_message: game.status === 'abandoned' ? 'Game was abandoned' : undefined,
          rounds: [],
        },
      };
    }

    const completedCount = jobs.filter((j) => j.status === 'round_created').length;
    const failedJobs = jobs.filter((j) => j.status === 'failed');
    const active = jobs.find((j) => j.status !== 'round_created' && j.status !== 'failed');
    const pendingJobs = jobs.filter((j) => j.status === 'pending');

    // Determine overall status:
    // - 'completed' if all required jobs are done (round_created)
    // - 'failed' only if the game status is 'pending' (still generating) AND all jobs are either failed or round_created AND we don't have enough rounds
    // - 'generating' if there are still pending/active jobs or we're still retrying
    let status: 'generating' | 'completed' | 'failed';
    
    if (completedCount === jobs.length) {
      status = 'completed';
    } else if (game?.status === 'in_progress' || game?.status === 'completed') {
      // Game has already started, meaning generation succeeded
      status = 'completed';
    } else if (active || pendingJobs.length > 0) {
      // Still generating - either active work or pending jobs remain
      status = 'generating';
    } else if (failedJobs.length > 0 && completedCount === 0) {
      // All jobs failed and none succeeded - true failure
      status = 'failed';
    } else {
      // Some jobs completed, some failed - still consider it generating
      // The backend will continue with remaining buffer questions
      status = 'generating';
    }

    // Only include error message if truly failed
    const errorMessage = status === 'failed' ? failedJobs[0]?.error_message : undefined;

    return {
      game_id: gameId,
      status,
      progress: {
        game_id: gameId,
        total_rounds: jobs.length,
        completed_rounds: completedCount,
        current_round: active?.round_number,
        current_status: active ? mapJobStatus(active.status) : undefined,
        error_message: errorMessage,
        rounds: jobs.map((j) => ({
          round_number: j.round_number,
          status: mapJobStatus(j.status),
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

    // Build query - exclude rejected games (all jobs failed with REJECTED: prefix)
    const rejectedSubquery = `
      NOT EXISTS (
        SELECT 1 FROM quiz_generation_jobs j 
        WHERE j.game_id = g.game_id 
        AND j.status = 'failed' 
        AND j.error_message LIKE 'REJECTED:%'
        AND NOT EXISTS (
          SELECT 1 FROM quiz_generation_jobs j2 
          WHERE j2.game_id = g.game_id 
          AND j2.status != 'failed'
        )
      )
    `;
    
    let whereClause = `WHERE ${rejectedSubquery}`;
    const params: any[] = [];

    if (status) {
      whereClause += ` AND g.status = $1`;
      params.push(status);
    }

    // Get total count
    const countResult = await postgresService.queryOne<{ count: string }>(
      `SELECT COUNT(*) as count FROM public.quiz_games g ${whereClause}`,
      params
    );
    const total = parseInt(countResult?.count ?? '0');

    // Get games with pagination
    const games = await postgresService.queryMany<QuizGame>(
      `SELECT g.* FROM public.quiz_games g
       ${whereClause}
       ORDER BY g.created_at DESC
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

  /**
   * Delete a quiz game and all related data
   */
  async deleteGame(gameId: string): Promise<void> {
    const game = await postgresService.queryOne<{ game_id: string }>(
      `SELECT game_id FROM public.quiz_games WHERE game_id = $1`,
      [gameId]
    );

    if (!game) {
      throw new Error('Game not found');
    }

    // Delete in order of dependencies
    await postgresService.query(
      `DELETE FROM public.quiz_answers WHERE round_id IN (SELECT round_id FROM public.quiz_rounds WHERE game_id = $1)`,
      [gameId]
    );
    await postgresService.query(`DELETE FROM public.quiz_rounds WHERE game_id = $1`, [gameId]);
    await postgresService.query(`DELETE FROM public.quiz_generation_jobs WHERE game_id = $1`, [gameId]);
    await postgresService.query(`DELETE FROM public.quiz_games WHERE game_id = $1`, [gameId]);
  }

  /**
   * Restart a game - reset to round 1, clear all answers but keep questions
   */
  async restartGame(gameId: string): Promise<QuizGameResponse> {
    const game = await postgresService.queryOne<QuizGame>(
      `SELECT * FROM public.quiz_games WHERE game_id = $1`,
      [gameId]
    );

    if (!game) {
      throw new Error('Game not found');
    }

    // Delete all player answers (this also resets scores since they're stored per-answer)
    await postgresService.query(
      `DELETE FROM public.quiz_answers WHERE round_id IN (SELECT round_id FROM public.quiz_rounds WHERE game_id = $1)`,
      [gameId]
    );

    // Reset game state
    await postgresService.query(
      `UPDATE public.quiz_games 
       SET status = 'in_progress', current_round = 1, completed_at = NULL 
       WHERE game_id = $1`,
      [gameId]
    );

    console.log(`🔄 Game ${gameId} restarted`);

    return this.getGame(gameId);
  }

  /**
   * Recover pending quiz generation jobs after server restart
   * Re-enqueues any games that were in the middle of generation
   */
  async recoverPendingJobs(): Promise<number> {
    console.log('🔄 Checking for pending quiz generation jobs...');
    
    type PendingGame = {
      game_id: string;
      num_rounds: number;
      difficulty: 'easy' | 'medium' | 'hard';
      category_name: string;
      topic: string | null;
      player_count: number;
    };

    const pendingGames = await postgresService.queryMany<PendingGame>(
      `SELECT g.game_id, g.num_rounds, g.difficulty,
              COALESCE(c.name, 'statistics') as category_name,
              g.topic,
              COALESCE(jsonb_array_length(g.player_names::jsonb), 1) as player_count
       FROM public.quiz_games g
       LEFT JOIN public.quiz_categories c ON g.category_id = c.category_id
       WHERE g.status = 'pending'
         -- Has incomplete jobs (not all round_created)
         AND EXISTS (
           SELECT 1 FROM quiz_generation_jobs j
           WHERE j.game_id = g.game_id
             AND j.status NOT IN ('round_created')
         )
         -- Exclude games where ALL jobs failed with REJECTED: prefix (topic was rejected)
         AND NOT (
           NOT EXISTS (
             SELECT 1 FROM quiz_generation_jobs j2
             WHERE j2.game_id = g.game_id
               AND j2.status != 'failed'
           )
           AND EXISTS (
             SELECT 1 FROM quiz_generation_jobs j3
             WHERE j3.game_id = g.game_id
               AND j3.status = 'failed'
               AND j3.error_message LIKE 'REJECTED:%'
           )
         )
       ORDER BY g.created_at ASC
       LIMIT 10`
    );

    if (pendingGames.length === 0) {
      console.log('✅ No pending quiz generation jobs found');
      return 0;
    }

    console.log(`🔄 Found ${pendingGames.length} pending quiz generation job(s), re-enqueueing...`);

    for (const game of pendingGames) {
      const category = game.topic ?? game.category_name;
      console.log(`   📋 Re-enqueueing game ${game.game_id} (${game.num_rounds} rounds, ${category})`);
      
      quizJobQueue.enqueue(() =>
        this.generateQuestionsForGame(game.game_id, {
          category,
          difficulty: game.difficulty,
          numRounds: game.num_rounds,
          numberOfPlayers: game.player_count,
        })
      );
    }

    return pendingGames.length;
  }
}

// Singleton instance
export const quizService = new QuizService();
