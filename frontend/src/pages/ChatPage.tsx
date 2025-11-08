import React from 'react';
import { ChatbotWindow } from '../components/chat/ChatbotWindow';
import styles from './ChatPage.module.css';

export const ChatPage: React.FC = () => {
  return (
    <div className={styles.chatPage}>
      <ChatbotWindow />
    </div>
  );
};



