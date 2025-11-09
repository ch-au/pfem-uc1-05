import type { FastifyInstance } from 'fastify';
import { quizService } from '../services/quiz/quiz.service.js';
import { z } from 'zod';

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

      return reply.send(progress);
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(404).send({ error: 'Generation progress not found' });
    }
  });
}
