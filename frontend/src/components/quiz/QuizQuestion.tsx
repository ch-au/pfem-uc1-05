import React from 'react';
import { User, Crown } from 'lucide-react';
import styles from './QuizQuestion.module.css';

export interface QuizQuestionProps {
  question: string;
  roundNumber: number;
  totalRounds: number;
  currentPlayer?: string;
  players?: string[];
  currentPlayerIndex?: number;
}

export const QuizQuestion: React.FC<QuizQuestionProps> = ({
  question,
  roundNumber,
  totalRounds,
  currentPlayer,
  players = [],
  currentPlayerIndex = 0,
}) => {
  const getPlayerOrder = () => {
    if (players.length === 0) return [];
    const ordered = [];
    for (let i = 0; i < players.length; i++) {
      const idx = (currentPlayerIndex + i) % players.length;
      ordered.push({
        name: players[idx],
        isCurrent: i === 0,
        turnNumber: i + 1,
      });
    }
    return ordered;
  };

  const orderedPlayers = getPlayerOrder();

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
          <div className={styles.progressTrack}>
            {Array.from({ length: totalRounds }, (_, i) => (
              <div 
                key={i}
                className={`${styles.progressStep} ${i + 1 < roundNumber ? styles.progressStepComplete : ''} ${i + 1 === roundNumber ? styles.progressStepCurrent : ''}`}
              >
                <span className={styles.progressStepNumber}>{i + 1}</span>
              </div>
            ))}
            {totalRounds > 1 && (
              <div className={styles.progressLine}>
                <div 
                  className={styles.progressLineFill} 
                  style={{ width: `${Math.min(100, Math.max(0, ((roundNumber - 1) / (totalRounds - 1)) * 100))}%` }}
                />
              </div>
            )}
          </div>
        </div>

        {orderedPlayers.length > 0 ? (
          <div className={styles.playerOverview}>
            <div className={styles.playerOverviewLabel}>Spieler</div>
            <div className={styles.playerList}>
              {orderedPlayers.map((player, idx) => (
                <div 
                  key={player.name}
                  className={`${styles.playerChip} ${player.isCurrent ? styles.playerChipActive : ''}`}
                >
                  {player.isCurrent && <Crown size={12} className={styles.crownIcon} />}
                  <span className={styles.playerInitial}>
                    {player.name.charAt(0).toUpperCase()}
                  </span>
                  <span className={styles.playerName}>{player.name}</span>
                  {!player.isCurrent && (
                    <span className={styles.turnIndicator}>+{idx}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : currentPlayer && (
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
