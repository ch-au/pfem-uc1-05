import React from 'react';
import { clsx } from 'clsx';
import type { QuizLeaderboardEntry } from '../../types/api';
import styles from './Leaderboard.module.css';

export interface LeaderboardProps {
  entries: QuizLeaderboardEntry[];
}

export const Leaderboard: React.FC<LeaderboardProps> = ({ entries }) => {
  return (
    <div className={styles.container}>
      <h3 className={styles.title}>Bestenliste</h3>
      <div className={styles.list}>
        {entries.map((entry, index) => (
          <div
            key={entry.player_name}
            className={clsx(
              styles.item,
              index === 0 && styles['item--first']
            )}
          >
            <span className={styles.rank}>{index + 1}.</span>
            <span className={styles.name}>{entry.player_name}</span>
            <span className={styles.score}>
              {entry.score} Punkte ({entry.correct_answers}/{entry.total_questions} richtig)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};



