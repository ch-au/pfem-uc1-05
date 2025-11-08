import React, { useEffect, useRef } from 'react';
import { ChatMessageComponent } from './ChatMessage';
import { TypingIndicator } from './TypingIndicator';
import type { ChatMessage } from '../../types/api';
import styles from './ChatContainer.module.css';

export interface ChatContainerProps {
  messages: ChatMessage[];
  isLoading?: boolean;
  emptyStateMessage?: string;
}

export const ChatContainer: React.FC<ChatContainerProps> = ({
  messages,
  isLoading = false,
  emptyStateMessage = 'Stelle eine Frage zur Geschichte von Mainz 05...',
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div ref={containerRef} className={styles.container}>
      {messages.length === 0 && !isLoading ? (
        <div className={styles.emptyState}>
          <p>{emptyStateMessage}</p>
        </div>
      ) : (
        <>
          {messages.map((message, index) => (
            <ChatMessageComponent key={index} message={message} />
          ))}
          {isLoading && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
};



