import React from 'react';
import { clsx } from 'clsx';
import styles from './QuizOption.module.css';

export interface QuizOptionProps {
  option: string;
  label: string;
  index: number;
  selected?: boolean;
  correct?: boolean;
  incorrect?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}

export const QuizOption: React.FC<QuizOptionProps> = ({
  option,
  label,
  index,
  selected = false,
  correct = false,
  incorrect = false,
  disabled = false,
  onClick,
}) => {
  const letter = String.fromCharCode(65 + index); // A, B, C, D

  return (
    <button
      className={clsx(
        styles.option,
        selected && styles['option--selected'],
        correct && styles['option--correct'],
        incorrect && styles['option--incorrect'],
        disabled && styles['option--disabled']
      )}
      onClick={onClick}
      disabled={disabled}
    >
      <span className={styles.letter}>{letter})</span>
      <span className={styles.label}>{label}</span>
    </button>
  );
};



