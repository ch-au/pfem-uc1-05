import React from 'react';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { User, ArrowRight } from 'lucide-react';
import styles from './PlayerHandoff.module.css';

interface PlayerHandoffProps {
  nextPlayer: string;
  roundNumber: number;
  totalRounds: number;
  onReady: () => void;
}

export const PlayerHandoff: React.FC<PlayerHandoffProps> = ({
  nextPlayer,
  roundNumber,
  totalRounds,
  onReady,
}) => {
  return (
    <Card variant="elevated" padding="lg" className={styles.container}>
      <div className={styles.content}>
        <div className={styles.icon}>
          <User size={48} />
        </div>
        
        <div className={styles.roundInfo}>
          Runde {roundNumber} von {totalRounds}
        </div>
        
        <h2 className={styles.title}>
          Gerät weitergeben
        </h2>
        
        <p className={styles.description}>
          Gib das Gerät an <strong>{nextPlayer}</strong> weiter
        </p>
        
        <div className={styles.warning}>
          Nicht hinschauen! Die Frage erscheint gleich.
        </div>
        
        <Button
          variant="primary"
          size="lg"
          onClick={onReady}
          className={styles.readyButton}
        >
          <span>Ich bin {nextPlayer}</span>
          <ArrowRight size={20} />
        </Button>
      </div>
    </Card>
  );
};
