import type { FastifyInstance } from 'fastify';
import { chatService } from '../services/chat/chat.service.js';
import { z } from 'zod';

const ChatMessageRequestSchema = z.object({
  session_id: z.string().uuid(),
  content: z.string().min(1).max(5000),
});

const CreateSessionSchema = z.object({});

export async function chatRoutes(fastify: FastifyInstance) {
  // Create a new chat session
  fastify.post('/chat/session', async (request, reply) => {
    try {
      const session = await chatService.createSession();
      return reply.code(201).send({
        session_id: session.session_id,
        created_at: session.created_at.toISOString(),
        expires_at: session.expires_at.toISOString(),
      });
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to create session' });
    }
  });

  // Get chat history
  fastify.get<{
    Params: { sessionId: string };
  }>('/chat/session/:sessionId', async (request, reply) => {
    try {
      const { sessionId } = request.params;

      const session = await chatService.getSession(sessionId);
      if (!session) {
        return reply.code(404).send({ error: 'Session not found' });
      }

      const messages = await chatService.getHistory(sessionId);

      return reply.send({
        session_id: session.session_id,
        messages: messages.map((msg) => ({
          message_id: msg.message_id,
          role: msg.role,
          content: msg.content,
          metadata: msg.metadata,
          created_at: msg.created_at.toISOString(),
        })),
      });
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to fetch history' });
    }
  });

  // Send a message
  fastify.post('/chat/message', async (request, reply) => {
    try {
      const body = ChatMessageRequestSchema.parse(request.body);

      const response = await chatService.processMessage(body);

      return reply.send(response);
    } catch (error: any) {
      if (error instanceof z.ZodError) {
        return reply.code(400).send({ error: 'Invalid request', details: error.errors });
      }

      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to process message' });
    }
  });

  // Delete a session
  fastify.delete<{
    Params: { sessionId: string };
  }>('/chat/session/:sessionId', async (request, reply) => {
    try {
      const { sessionId } = request.params;

      await chatService.deleteSession(sessionId);

      return reply.code(204).send();
    } catch (error: any) {
      fastify.log.error(error);
      return reply.code(500).send({ error: 'Failed to delete session' });
    }
  });
}
