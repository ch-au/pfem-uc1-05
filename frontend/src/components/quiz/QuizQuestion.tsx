import React from 'react';
import styles from './QuizQuestion.module.css';

export interface QuizQuestionProps {
  question: string;
  roundNumber: number;
  totalRounds: number;
  currentPlayer?: string;
}

export const QuizQuestion: React.FC<QuizQuestionProps> = ({
  question,
  roundNumber,
  totalRounds,
  currentPlayer,
}) => {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.info}>
          <div className={styles.roundInfo}>
            Runde <span className={styles.roundNumber}>{roundNumber}</span> von{' '}
            <span className={styles.totalRounds}>{totalRounds}</span>
          </div>
          {currentPlayer && (
            <div className={styles.playerInfo}>Spieler: {currentPlayer}</div>
          )}
        </div>
      </div>
      <h2 className={styles.question}>{question}</h2>
    </div>
  );
};



