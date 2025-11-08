import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { clsx } from 'clsx';
import { MessageSquare, Trophy, User } from 'lucide-react';
import styles from './MobileNav.module.css';

export const MobileNav: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className={styles.mobileNav}>
      <button
        className={clsx(
          styles.navItem,
          (isActive('/') || isActive('/chat')) && styles['navItem--active']
        )}
        onClick={() => navigate('/')}
      >
        <MessageSquare size={24} />
        <span>Chat</span>
      </button>
      <button
        className={clsx(
          styles.navItem,
          isActive('/quiz') && styles['navItem--active']
        )}
        onClick={() => navigate('/quiz')}
      >
        <Trophy size={24} />
        <span>Quiz</span>
      </button>
      <button
        className={clsx(
          styles.navItem,
          isActive('/profile') && styles['navItem--active']
        )}
        onClick={() => navigate('/profile')}
      >
        <User size={24} />
        <span>Profil</span>
      </button>
    </nav>
  );
};



