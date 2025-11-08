import { useEffect, useState, useCallback, useRef } from 'react';
import { useChatStore } from '../store/chatStore';
import { chatService } from '../services/chatService';
import type { ChatMessage } from '../types/api';

export interface UseChatbotWindowReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  isConnected: boolean;
  error: string | null;
  showWelcome: boolean;
  showScrollButton: boolean;
  sendMessage: (content: string) => Promise<void>;
  scrollToBottom: () => void;
  clearChat: () => void;
  handleFeedback: (messageId: string, feedback: 'positive' | 'negative') => void;
}

export const useChatbotWindow = (): UseChatbotWindowReturn => {
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
    clearMessages,
  } = useChatStore();

  const [isConnected, setIsConnected] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize session on mount
  useEffect(() => {
    initializeSession();
  }, []);

  // Handle scroll detection
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      setShowScrollButton(!isNearBottom && messages.length > 3);
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [messages.length]);

  const initializeSession = async () => {
    try {
      setLoading(true);
      setError(null);
      const newSessionId = await chatService.createSession();
      setSessionId(newSessionId);
      setIsConnected(true);

      // Try to load history
      try {
        const history = await chatService.getHistory(newSessionId);
        if (history.length > 0) {
          setMessages(history);
        }
      } catch (historyError) {
        // History load failed, but session is still valid
        console.warn('Failed to load history:', historyError);
      }
    } catch (err) {
      console.error('Failed to initialize session:', err);
      setError('Verbindung konnte nicht hergestellt werden');
      setIsConnected(false);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = useCallback(
    async (content: string) => {
      if (!sessionId || isLoading || !content.trim()) return;

      const userMessage: ChatMessage = {
        role: 'user',
        content: content.trim(),
        timestamp: new Date().toISOString(),
      };

      addMessage(userMessage);
      setLoading(true);
      setError(null);

      // Scroll to bottom after user message
      setTimeout(() => scrollToBottom(), 100);

      try {
        const response = await chatService.sendMessage(sessionId, content.trim());

        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: response.content,
          timestamp: response.created_at,
          metadata: response.metadata,
        };

        addMessage(assistantMessage);

        // Scroll to bottom after assistant message
        setTimeout(() => scrollToBottom(), 100);
      } catch (err) {
        console.error('Failed to send message:', err);
        const errorMessage: ChatMessage = {
          role: 'error',
          content:
            'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
          timestamp: new Date().toISOString(),
        };
        addMessage(errorMessage);
        setError('Nachricht konnte nicht gesendet werden');
      } finally {
        setLoading(false);
      }
    },
    [sessionId, isLoading, addMessage, setLoading, setError]
  );

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const clearChat = useCallback(() => {
    clearMessages();
    setError(null);
  }, [clearMessages, setError]);

  const handleFeedback = useCallback(
    (messageId: string, feedback: 'positive' | 'negative') => {
      // TODO: Implement feedback submission to backend
      console.log('Feedback received:', { messageId, feedback });
      // This could send to analytics or a feedback endpoint
    },
    []
  );

  return {
    messages,
    isLoading,
    isConnected,
    error,
    showWelcome: messages.length === 0 && !isLoading,
    showScrollButton,
    sendMessage,
    scrollToBottom,
    clearChat,
    handleFeedback,
  };
};
