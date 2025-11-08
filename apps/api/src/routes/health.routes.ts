import type { FastifyInstance } from 'fastify';
import { postgresService } from '../services/database/postgres.service.js';
import { geminiService } from '../services/ai/gemini.service.js';
import { langfuseService } from '../services/ai/langfuse.service.js';

export async function healthRoutes(fastify: FastifyInstance) {
  // Basic health check
  fastify.get('/health', async (request, reply) => {
    return reply.send({
      status: 'ok',
      timestamp: new Date().toISOString(),
    });
  });

  // Detailed health check
  fastify.get('/health/detailed', async (request, reply) => {
    const checks = {
      database: false,
      gemini: false,
      langfuse: langfuseService.isActive(),
    };

    try {
      checks.database = await postgresService.healthCheck();
    } catch (error) {
      fastify.log.error('Database health check failed:', error);
    }

    try {
      checks.gemini = await geminiService.healthCheck();
    } catch (error) {
      fastify.log.error('Gemini health check failed:', error);
    }

    const allHealthy = checks.database && checks.gemini;

    return reply.code(allHealthy ? 200 : 503).send({
      status: allHealthy ? 'healthy' : 'degraded',
      timestamp: new Date().toISOString(),
      checks,
    });
  });
}
