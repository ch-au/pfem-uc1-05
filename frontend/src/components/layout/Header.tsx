import React from 'react';
import { User } from 'lucide-react';
import { IconButton } from '../ui/IconButton';
import styles from './Header.module.css';

export interface HeaderProps {
  onProfileClick?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onProfileClick }) => {
  return (
    <header className={styles.header}>
      <div className={styles.mainNav}>
        <div className={styles.navContent}>
          <div className={styles.logoSection}>
            <div className={styles.logo}>05</div>
            <div className={styles.appTitle}>Dein 05 Fan-Quiz</div>
          </div>
          <IconButton
            variant="default"
            size="md"
            onClick={onProfileClick}
            aria-label="Profil"
          >
            <User size={20} />
          </IconButton>
        </div>
      </div>
    </header>
  );
};



