import React from 'react';
import { User } from 'lucide-react';
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
  const progressPercent = ((roundNumber - 1) / totalRounds) * 100;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.progressSection}>
          <div className={styles.progressInfo}>
            <span className={styles.roundLabel}>Runde</span>
            <span className={styles.roundCurrent}>{roundNumber}</span>
            <span className={styles.roundSeparator}>/</span>
            <span className={styles.roundTotal}>{totalRounds}</span>
          </div>
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill} 
              style={{ width: `${progressPercent}%` }}
            />
            <div 
              className={styles.progressMarker} 
              style={{ left: `${(roundNumber / totalRounds) * 100}%` }}
            />
          </div>
          <div className={styles.stepIndicators}>
            {Array.from({ length: totalRounds }, (_, i) => (
              <div 
                key={i}
                className={`${styles.stepDot} ${i + 1 < roundNumber ? styles.stepComplete : ''} ${i + 1 === roundNumber ? styles.stepCurrent : ''}`}
              />
            ))}
          </div>
        </div>

        {currentPlayer && (
          <div className={styles.playerBadge}>
            <User size={14} />
            <span>{currentPlayer}</span>
          </div>
        )}
      </div>

      <h2 className={styles.question}>{question}</h2>
    </div>
  );
};
