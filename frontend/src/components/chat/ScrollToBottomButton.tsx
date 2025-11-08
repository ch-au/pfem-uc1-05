import React from 'react';
import { ArrowDown } from 'lucide-react';
import styles from './ScrollToBottomButton.module.css';

export interface ScrollToBottomButtonProps {
  onClick: () => void;
  unreadCount?: number;
}

export const ScrollToBottomButton: React.FC<ScrollToBottomButtonProps> = ({
  onClick,
  unreadCount = 0,
}) => {
  return (
    <button
      className={styles.button}
      onClick={onClick}
      aria-label="Zum Ende scrollen"
      title="Zum Ende scrollen"
    >
      {unreadCount > 0 && (
        <span className={styles.badge}>{unreadCount}</span>
      )}
      <ArrowDown size={20} />
    </button>
  );
};
