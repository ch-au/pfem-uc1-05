import React from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Check, X, SkipForward } from 'lucide-react';
import styles from './RoundResults.module.css';

interface PlayerResult {
  playerName: string;
  answer: string;
  correct: boolean;
  pointsEarned: number;
}

interface RoundResultsProps {
  roundNumber: number;
  totalRounds: number;
  correctAnswer: string;
  explanation?: string;
  playerResults: PlayerResult[];
  onNextRound: () => void;
  isLastRound: boolean;
}

export const RoundResults: React.FC<RoundResultsProps> = ({
  roundNumber,
  totalRounds,
  correctAnswer,
  explanation,
  playerResults,
  onNextRound,
  isLastRound,
}) => {
  return (
    <Card variant="elevated" padding="lg" className={styles.container}>
      <div className={styles.header}>
        <span className={styles.roundLabel}>Runde {roundNumber} von {totalRounds}</span>
        <h2 className={styles.title}>Ergebnisse</h2>
      </div>

      <div className={styles.answer}>
        <div className={styles.answerLabel}>Richtige Antwort</div>
        <div className={styles.answerText}>{correctAnswer}</div>
        {explanation && (
          <div className={styles.explanation}>{explanation}</div>
        )}
      </div>

      <div className={styles.results}>
        {playerResults.map((result, index) => (
          <div
            key={result.playerName}
            className={`${styles.resultRow} ${result.correct ? styles.correct : styles.incorrect}`}
          >
            <div className={styles.resultIcon}>
              {result.correct ? <Check size={20} /> : <X size={20} />}
            </div>
            <div className={styles.resultInfo}>
              <span className={styles.playerName}>{result.playerName}</span>
              <span className={styles.playerAnswer}>{result.answer}</span>
            </div>
            <div className={styles.points}>
              {result.correct ? `+${result.pointsEarned}` : '0'}
            </div>
          </div>
        ))}
      </div>

      <Button
        variant="primary"
        size="lg"
        onClick={onNextRound}
        className={styles.nextButton}
      >
        <span>{isLastRound ? 'Endergebnis anzeigen' : 'Nächste Runde'}</span>
        <SkipForward size={20} />
      </Button>
    </Card>
  );
};
