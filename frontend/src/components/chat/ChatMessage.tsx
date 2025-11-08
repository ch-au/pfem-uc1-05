import React from 'react';
import { clsx } from 'clsx';
import { Avatar } from '../ui/Avatar';
import type { ChatMessage } from '../../types/api';
import styles from './ChatMessage.module.css';

export interface ChatMessageProps {
  message: ChatMessage;
}

export const ChatMessageComponent: React.FC<ChatMessageProps> = ({ message }) => {
  const { role, content, timestamp } = message;

  const formatTime = (timestamp?: string) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div
      className={clsx(
        styles.message,
        styles[`message--${role}`],
        'animate-slide-in'
      )}
    >
      {role !== 'system' && (
        <Avatar
          variant={role === 'user' ? 'user' : 'bot'}
          size="md"
        />
      )}
      <div className={styles.content}>
        <div
          className={clsx(
            styles.bubble,
            styles[`bubble--${role}`]
          )}
        >
          {content}
        </div>
        {timestamp && role !== 'system' && (
          <div className={clsx(styles.timestamp, styles[`timestamp--${role}`])}>
            {formatTime(timestamp)}
          </div>
        )}
      </div>
    </div>
  );
};



