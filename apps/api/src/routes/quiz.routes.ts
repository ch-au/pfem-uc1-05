import type { FastifyInstance } from 'fastify';
import { quizService } from '../services/quiz/quiz.service.js';
import { z } from 'zod';

// Track last progress logged per game to avoid noisy logs
const progressLogCache: Record<
  string,
  { status: string; completed: number; total: number; currentStatus?: string | null }
> = {};

const CreateGameSchema = z.object({
  topic: z.string().optional(),
  difficulty: z.enum(['easy', 'medium', 'hard']),
  num_rounds: z.number().int().min(1).max(20),
  game_mode: z.enum(['classic', 'speed', 'survival']).optional(),
  category_id: z.string().uuid().optional(),
  player_names: z.array(z.string()).min(1).max(10),
});

const SubmitAnswerSchema = z.object({
  player_name: z.string().min(1).max(100),
  answer: z.string().min(1).max(500),
  time_taken: z.number().min(0).max(300),
});

export async function quizRoutes(fastify: FastifyInstance) {
  // Create a new game
  fastify.post('/quiz/game', async (request, reply) => {
    try {
      const body = CreateGameSchema.parse(request.body);

      const game = await quizService.createGame(body);
      fastify.log.info(
        {
          gameId: game.game_id,
          generationJobId: game.generation_job_id,
          generationStatus: game.generation_status,
        },
        'quiz game created and generation enqueued'
      );

      return reply.code(201).send(game);
    } catch (error: any) {
      if (error instanceof z.ZodError) {
        return reply.code(400).send({ error: 'Invalid request', details: error.errors });
      }

      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to create game' });
    }
  });

  // Start a game
  fastify.post<{
    Params: { gameId: string };
  }>('/quiz/game/:gameId/start', async (request, reply) => {
    try {
      const { gameId } = request.params;

      const game = await quizService.startGame(gameId);

      return reply.send(game);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to start game' });
    }
  });

  // Get game state
  fastify.get<{
    Params: { gameId: string };
  }>('/quiz/game/:gameId', async (request, reply) => {
    try {
      const { gameId } = request.params;

      const game = await quizService.getGame(gameId);

      return reply.send(game);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(404).send({ error: 'Game not found' });
    }
  });

  // Get current question
  fastify.get<{
    Params: { gameId: string };
  }>('/quiz/game/:gameId/question', async (request, reply) => {
    try {
      const { gameId } = request.params;

      const question = await quizService.getCurrentQuestion(gameId);

      return reply.send(question);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(404).send({ error: 'Question not found' });
    }
  });

  // Submit an answer
  fastify.post<{
    Params: { gameId: string };
  }>('/quiz/game/:gameId/answer', async (request, reply) => {
    try {
      const { gameId } = request.params;
      const body = SubmitAnswerSchema.parse(request.body);

      // Get current game state to determine round number
      const game = await quizService.getGame(gameId);
      const roundNumber = game.current_round;

      const result = await quizService.submitAnswer(gameId, roundNumber, body);

      return reply.send(result);
    } catch (error: any) {
      if (error instanceof z.ZodError) {
        return reply.code(400).send({ error: 'Invalid request', details: error.errors });
      }

      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to submit answer' });
    }
  });

  // Advance to next round
  fastify.post<{
    Params: { gameId: string };
  }>('/quiz/game/:gameId/next', async (request, reply) => {
    try {
      const { gameId } = request.params;

      const game = await quizService.nextRound(gameId);

      return reply.send(game);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to advance round' });
    }
  });

  // Get leaderboard
  fastify.get<{
    Params: { gameId: string };
  }>('/quiz/game/:gameId/leaderboard', async (request, reply) => {
    try {
      const { gameId } = request.params;

      const leaderboard = await quizService.getLeaderboard(gameId);

      return reply.send(leaderboard);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to fetch leaderboard' });
    }
  });

  // Get quiz generation progress
  fastify.get<{
    Params: { gameId: string };
  }>('/quiz/game/:gameId/progress', async (request, reply) => {
    try {
      const { gameId } = request.params;

      const progress = await quizService.getGenerationProgress(gameId);
      const last = progressLogCache[gameId];
      const current = {
        status: progress.status,
        completed: progress.progress.completed_rounds,
        total: progress.progress.total_rounds,
        currentStatus: progress.progress.current_status,
      };

      // Only log when something changes to keep logs readable
      if (
        !last ||
        last.status !== current.status ||
        last.completed !== current.completed ||
        last.currentStatus !== current.currentStatus
      ) {
        fastify.log.info(
          {
            gameId,
            status: current.status,
            completed: current.completed,
            total: current.total,
            currentStatus: current.currentStatus,
          },
          'quiz generation progress'
        );
        progressLogCache[gameId] = current;
      }

      return reply.send(progress);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(404).send({ error: 'Generation progress not found' });
    }
  });

  // Get game history (all games or filtered)
  fastify.get<{
    Querystring: { status?: string; limit?: string; offset?: string };
  }>('/quiz/games', async (request, reply) => {
    try {
      const { status, limit, offset } = request.query;

      const result = await quizService.getGameHistory({
        status: status as any,
        limit: limit ? parseInt(limit) : undefined,
        offset: offset ? parseInt(offset) : undefined,
      });

      return reply.send(result);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to fetch game history' });
    }
  });

  // Get completed games only
  fastify.get<{
    Querystring: { limit?: string; offset?: string };
  }>('/quiz/games/completed', async (request, reply) => {
    try {
      const { limit, offset } = request.query;

      const result = await quizService.getCompletedGames(
        limit ? parseInt(limit) : undefined,
        offset ? parseInt(offset) : undefined
      );

      return reply.send(result);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to fetch completed games' });
    }
  });

  // Global leaderboard
  fastify.get<{
    Querystring: { limit?: string };
  }>('/quiz/leaderboard', async (request, reply) => {
    try {
      const { limit } = request.query;
      const entries = await quizService.getGlobalLeaderboard(limit ? parseInt(limit) : 20);
      return reply.send({ leaderboard: entries });
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to fetch global leaderboard' });
    }
  });

  // Delete a game
  fastify.delete<{
    Params: { gameId: string };
  }>('/quiz/game/:gameId', async (request, reply) => {
    try {
      const { gameId } = request.params;

      await quizService.deleteGame(gameId);
      fastify.log.info({ gameId }, 'quiz game deleted');

      return reply.code(204).send();
    } catch (error: any) {
      fastify.log.error(error);
      if (error.message === 'Game not found') {
        return reply.code(404).send({ error: 'Game not found' });
      }
      return reply.code(500).send({ error: 'Failed to delete game' });
    }
  });
}
