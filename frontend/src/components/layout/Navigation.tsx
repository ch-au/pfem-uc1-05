import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { clsx } from 'clsx';
import { MessageSquare, Trophy } from 'lucide-react';
import styles from './Navigation.module.css';

export const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className={styles.navigation}>
      <button
        className={clsx(
          styles.navButton,
          isActive('/') && styles['navButton--active']
        )}
        onClick={() => navigate('/')}
      >
        <MessageSquare size={20} />
        <span>Chatbot</span>
      </button>
      <button
        className={clsx(
          styles.navButton,
          isActive('/quiz') && styles['navButton--active']
        )}
        onClick={() => navigate('/quiz')}
      >
        <Trophy size={20} />
        <span>Quiz</span>
      </button>
    </nav>
  );
};



