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
            <div className={styles.logoContainer}>
              <img 
                src="/mainz05-logo.svg" 
                alt="Mainz 05 Logo" 
                className={styles.logoImage}
              />
            </div>
            <div className={styles.titleContainer}>
              <span className={styles.clubName}>1. FSV MAINZ 05</span>
              <h1 className={styles.appTitle}>FAN-QUIZ</h1>
            </div>
          </div>
          
          <div className={styles.actions}>
            <IconButton
              variant="ghost"
              className={styles.profileButton}
              onClick={onProfileClick}
              aria-label="Profil"
            >
              <User size={24} />
            </IconButton>
          </div>
        </div>
      </div>
    </header>
  );
};
