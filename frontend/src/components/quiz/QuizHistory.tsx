import React from 'react';
import { Clock, Target } from 'lucide-react';
import type { QuizGameState } from '../../types/api';
import styles from './QuizHistory.module.css';

export interface QuizHistoryProps {
  games: QuizGameState[];
  onSelectGame?: (gameId: string) => void;
}

const statusLabels: Record<string, string> = {
  completed: 'Beendet',
  in_progress: 'Läuft',
  pending: 'Wartet',
  abandoned: 'Abgebrochen',
};

const difficultyLabels: Record<string, string> = {
  easy: 'Einfach',
  medium: 'Mittel',
  hard: 'Schwer',
};

export const QuizHistory: React.FC<QuizHistoryProps> = ({ games, onSelectGame }) => {
  if (games.length === 0) {
    return (
      <div className={styles.container}>
        <h3 className={styles.title}>
          <Clock size={20} />
          Bisherige Spiele
        </h3>
        <div className={styles.emptyState}>
          Noch keine Spiele vorhanden. Starte dein erstes Quiz!
        </div>
      </div>
    );
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>
        <Clock size={20} />
        Bisherige Spiele
      </h3>
      <div className={styles.list}>
        {games.map((game) => (
          <div
            key={game.game_id}
            className={styles.item}
            onClick={() => onSelectGame?.(game.game_id)}
          >
            <div className={styles.itemInfo}>
              <div className={styles.itemTitle}>
                {game.topic || 'Quiz'} - {difficultyLabels[game.difficulty]}
              </div>
              <div className={styles.itemMeta}>
                <span>
                  <Target size={14} style={{ display: 'inline', marginRight: '0.25rem' }} />
                  Runde {game.current_round}/{game.num_rounds}
                </span>
                <span>{formatDate(game.created_at)}</span>
              </div>
            </div>
            <div className={`${styles.itemStatus} ${styles[`itemStatus--${game.status}`]}`}>
              {statusLabels[game.status] || game.status}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
