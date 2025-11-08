import React from 'react';
import { Avatar } from '../ui/Avatar';
import styles from './TypingIndicator.module.css';

export const TypingIndicator: React.FC = () => {
  return (
    <div className={`${styles.typingIndicator} animate-slide-in`}>
      <Avatar variant="bot" size="md" />
      <div className={styles.content}>
        <div className={styles.bubble}>
          <div className={styles.dots}>
            <div className={styles.dot} />
            <div className={styles.dot} />
            <div className={styles.dot} />
          </div>
          <span className={styles.text}>tippt...</span>
        </div>
      </div>
    </div>
  );
};



