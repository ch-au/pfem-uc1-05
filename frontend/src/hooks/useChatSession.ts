import { useEffect } from 'react';
import { chatService } from '../services/chatService';
import { useChatStore } from '../store/chatStore';
import type { ChatMessage } from '../types/api';

export const useChatSession = () => {
  const {
    sessionId,
    messages,
    isLoading,
    error,
    setSessionId,
    addMessage,
    setMessages,
    setLoading,
    setError,
  } = useChatStore();

  // Initialize session on mount
  useEffect(() => {
    if (!sessionId) {
      initializeSession();
    }
  }, []);

  const initializeSession = async () => {
    try {
      setLoading(true);
      setError(null);
      const newSessionId = await chatService.createSession();
      setSessionId(newSessionId);
      
      // Load existing history if available
      const history = await chatService.getHistory(newSessionId);
      if (history.length > 0) {
        setMessages(history);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
      console.error('Failed to initialize chat session:', err);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async (content: string) => {
    if (!sessionId || isLoading) return;

    // Add user message immediately
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    addMessage(userMessage);

    try {
      setLoading(true);
      setError(null);

      const response = await chatService.sendMessage(sessionId, content);

      // Add assistant response
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.answer,
        timestamp: new Date().toISOString(),
        metadata: {
          sources: response.sources,
          confidence: response.confidence,
          is_data_query: response.is_data_query,
        },
      };
      addMessage(assistantMessage);

      // Add system message if SQL query was used
      if (response.sql_query && response.sources && response.sources.length > 0) {
        const sqlPreview = response.sql_query.substring(0, 80);
        const systemMessage: ChatMessage = {
          role: 'system',
          content: `SQL: ${sqlPreview}...`,
          timestamp: new Date().toISOString(),
        };
        addMessage(systemMessage);
      }
    } catch (err) {
      const errorMessage: ChatMessage = {
        role: 'error',
        content: `Fehler: ${err instanceof Error ? err.message : 'Unknown error'}`,
        timestamp: new Date().toISOString(),
      };
      addMessage(errorMessage);
      setError(err instanceof Error ? err.message : 'Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  return {
    sessionId,
    messages,
    isLoading,
    error,
    sendMessage,
    initializeSession,
  };
};

