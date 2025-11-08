import Fastify from 'fastify';
import cors from '@fastify/cors';
import { env } from './config/env.js';
import { chatRoutes } from './routes/chat.routes.js';
import { quizRoutes } from './routes/quiz.routes.js';
import { healthRoutes } from './routes/health.routes.js';
import { postgresService } from './services/database/postgres.service.js';
import { langfuseService } from './services/ai/langfuse.service.js';

// Create Fastify instance
const fastify = Fastify({
  logger: {
    level: env.NODE_ENV === 'production' ? 'info' : 'debug',
    transport:
      env.NODE_ENV === 'development'
        ? {
            target: 'pino-pretty',
            options: {
              translateTime: 'HH:MM:ss Z',
              ignore: 'pid,hostname',
            },
          }
        : undefined,
  },
});

// Register CORS
await fastify.register(cors, {
  origin: env.NODE_ENV === 'production' ? false : true, // Allow all in dev
  credentials: true,
});

// Register routes
await fastify.register(healthRoutes);
await fastify.register(chatRoutes, { prefix: '/api' });
await fastify.register(quizRoutes, { prefix: '/api' });

// Global error handler
fastify.setErrorHandler((error, _request, reply) => {
  fastify.log.error(error);

  const statusCode = error.statusCode ?? 500;
  const message = statusCode === 500 ? 'Internal Server Error' : error.message;

  reply.code(statusCode).send({
    error: message,
    statusCode,
    ...(env.NODE_ENV === 'development' && { stack: error.stack }),
  });
});

// Graceful shutdown
const gracefulShutdown = async () => {
  fastify.log.info('Shutting down gracefully...');

  try {
    await langfuseService.shutdown();
    await postgresService.close();
    await fastify.close();
    fastify.log.info('Shutdown complete');
    process.exit(0);
  } catch (error) {
    fastify.log.error({ error }, 'Error during shutdown');
    process.exit(1);
  }
};

process.on('SIGTERM', gracefulShutdown);
process.on('SIGINT', gracefulShutdown);

// Start server
const start = async () => {
  try {
    await fastify.listen({
      port: env.API_PORT,
      host: env.API_HOST,
    });

    fastify.log.info(`🚀 API Server running at http://${env.API_HOST}:${env.API_PORT}`);
    fastify.log.info(`📊 Health check: http://${env.API_HOST}:${env.API_PORT}/health`);
    fastify.log.info(`🔥 Gemini Model: ${env.GEMINI_MODEL}`);
    fastify.log.info(`📡 Langfuse: ${langfuseService.isActive() ? 'Enabled' : 'Disabled (using local prompts)'}`);
  } catch (error) {
    fastify.log.error(error);
    process.exit(1);
  }
};

start();
