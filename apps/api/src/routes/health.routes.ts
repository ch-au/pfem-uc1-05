import type { FastifyInstance } from 'fastify';
import { postgresService } from '../services/database/postgres.service.js';
import { openRouterService } from '../services/ai/openrouter.service.js';
import { langfuseService } from '../services/ai/langfuse.service.js';

export async function healthRoutes(fastify: FastifyInstance) {
  // Basic health check
  fastify.get('/health', async (_request, reply) => {
    return reply.send({
      status: 'ok',
      timestamp: new Date().toISOString(),
    });
  });

  // Detailed health check
  fastify.get('/health/detailed', async (_request, reply) => {
    const checks = {
      database: false,
      openrouter: false,
      langfuse: langfuseService.isActive(),
    };

    try {
      checks.database = await postgresService.healthCheck();
    } catch (error) {
      fastify.log.error({ error }, 'Database health check failed');
    }

    try {
      checks.openrouter = await openRouterService.healthCheck();
    } catch (error) {
      fastify.log.error({ error }, 'OpenRouter health check failed');
    }

    const allHealthy = checks.database && checks.openrouter;

    return reply.code(allHealthy ? 200 : 503).send({
      status: allHealthy ? 'healthy' : 'degraded',
      timestamp: new Date().toISOString(),
      checks,
    });
  });
}
