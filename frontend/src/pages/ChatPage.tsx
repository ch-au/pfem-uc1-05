import React from 'react';
import { Card } from '../components/ui/Card';
import { ChatContainer } from '../components/chat/ChatContainer';
import { ChatInput } from '../components/chat/ChatInput';
import { useChatSession } from '../hooks/useChatSession';
import styles from './ChatPage.module.css';

export const ChatPage: React.FC = () => {
  const { messages, isLoading, sendMessage } = useChatSession();

  return (
    <div className={styles.chatPage}>
      <Card variant="elevated" padding="md" className={styles.chatCard}>
        <div className={styles.chatContainer}>
          <ChatContainer
            messages={messages}
            isLoading={isLoading}
          />
          <ChatInput
            onSend={sendMessage}
            isLoading={isLoading}
          />
        </div>
      </Card>
    </div>
  );
};



