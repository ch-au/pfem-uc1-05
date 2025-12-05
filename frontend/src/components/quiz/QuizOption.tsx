import React from 'react';
import { clsx } from 'clsx';
import { Check, X } from 'lucide-react';
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
  const letter = String.fromCharCode(65 + index);

  const renderBadgeContent = () => {
    if (correct) {
      return <Check size={16} strokeWidth={3} />;
    }
    if (incorrect) {
      return <X size={16} strokeWidth={3} />;
    }
    return letter;
  };

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
      <span className={styles.badge}>{renderBadgeContent()}</span>
      <span className={styles.label}>{label}</span>
      {(correct || incorrect) && (
        <span className={styles.indicator}>
          {correct ? <Check size={20} strokeWidth={2.5} /> : <X size={20} strokeWidth={2.5} />}
        </span>
      )}
    </button>
  );
};
