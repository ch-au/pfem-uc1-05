import React, { useState } from 'react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Card } from '../ui/Card';
import styles from './QuizSetup.module.css';

export interface QuizSetupProps {
  onSubmit: (data: {
    topic?: string;
    difficulty: 'easy' | 'medium' | 'hard';
    numRounds: number;
    playerNames: string[];
  }) => void;
  isLoading?: boolean;
}

export const QuizSetup: React.FC<QuizSetupProps> = ({ onSubmit, isLoading }) => {
  const [topic, setTopic] = useState('');
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard'>('medium');
  const [numRounds, setNumRounds] = useState(5);
  const [playerNames, setPlayerNames] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const players = playerNames
      .split(',')
      .map((p) => p.trim())
      .filter((p) => p.length > 0);

    if (players.length === 0) {
      alert('Bitte gib mindestens einen Spieler ein');
      return;
    }

    onSubmit({
      topic: topic.trim() || undefined,
      difficulty,
      numRounds,
      playerNames: players,
    });
  };

  return (
    <Card variant="elevated" padding="md">
      <h2 className={styles.title}>Neues Quiz erstellen</h2>
      <form onSubmit={handleSubmit} className={styles.form}>
        <div className={styles.field}>
          <Input
            label="Thema (optional)"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="z.B. Spieler, Spiele, Tore"
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Schwierigkeit</label>
          <select
            className={styles.select}
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value as 'easy' | 'medium' | 'hard')}
          >
            <option value="easy">Einfach</option>
            <option value="medium">Mittel</option>
            <option value="hard">Schwer</option>
          </select>
        </div>
        <div className={styles.field}>
          <Input
            label="Anzahl Runden"
            type="number"
            value={numRounds}
            onChange={(e) => setNumRounds(parseInt(e.target.value) || 5)}
            min={1}
            max={20}
          />
        </div>
        <div className={styles.field}>
          <Input
            label="Spieler (kommagetrennt)"
            value={playerNames}
            onChange={(e) => setPlayerNames(e.target.value)}
            placeholder="Alice, Bob"
          />
        </div>
        <Button
          type="submit"
          variant="primary"
          size="lg"
          isLoading={isLoading}
          className={styles.submitButton}
        >
          Quiz starten
        </Button>
      </form>
    </Card>
  );
};



