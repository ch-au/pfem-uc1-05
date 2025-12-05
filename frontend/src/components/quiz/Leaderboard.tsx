import React from 'react';
import { clsx } from 'clsx';
import { Trophy, Medal } from 'lucide-react';
import type { QuizLeaderboardEntry } from '../../types/api';
import styles from './Leaderboard.module.css';

export interface LeaderboardProps {
  entries: QuizLeaderboardEntry[];
  showTitle?: boolean;
}

const getInitials = (name: string): string => {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
};

export const Leaderboard: React.FC<LeaderboardProps> = ({ entries, showTitle = false }) => {
  const getRankClass = (index: number) => {
    switch (index) {
      case 0: return styles['item--gold'];
      case 1: return styles['item--silver'];
      case 2: return styles['item--bronze'];
      default: return '';
    }
  };

  const getRankIcon = (index: number) => {
    if (index === 0) return <Trophy size={16} />;
    if (index <= 2) return <Medal size={16} />;
    return null;
  };

  return (
    <div className={styles.container}>
      {showTitle && (
        <h3 className={styles.title}>
          <Trophy size={18} />
          Bestenliste
        </h3>
      )}
      <div className={styles.list}>
        {entries.map((entry, index) => (
          <div
            key={entry.player_name}
            className={clsx(styles.item, getRankClass(index))}
          >
            <div className={styles.leftSection}>
              <div className={clsx(styles.avatar, getRankClass(index))}>
                {getInitials(entry.player_name)}
              </div>
              <div className={styles.playerInfo}>
                <span className={styles.name}>{entry.player_name}</span>
                <span className={styles.stats}>
                  {entry.correct_answers}/{entry.total_questions} richtig
                </span>
              </div>
            </div>
            <div className={styles.rightSection}>
              <div className={styles.scoreWrapper}>
                {getRankIcon(index)}
                <span className={styles.score}>{entry.score}</span>
              </div>
              <span className={styles.pointsLabel}>Punkte</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
