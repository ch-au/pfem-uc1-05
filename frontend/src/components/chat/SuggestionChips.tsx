import React from 'react';
import { Sparkles } from 'lucide-react';
import styles from './SuggestionChips.module.css';

export interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
  maxVisible?: number;
}

export const SuggestionChips: React.FC<SuggestionChipsProps> = ({
  suggestions,
  onSelect,
  maxVisible = 3,
}) => {
  if (suggestions.length === 0) return null;

  const visibleSuggestions = suggestions.slice(0, maxVisible);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Sparkles size={14} />
        <span className={styles.label}>Vorschläge:</span>
      </div>
      <div className={styles.chips}>
        {visibleSuggestions.map((suggestion, index) => (
          <button
            key={index}
            className={styles.chip}
            onClick={() => onSelect(suggestion)}
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
};
