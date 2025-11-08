import React from 'react';
import { MessageCircle, History, Trophy, Users, Calendar, Sparkles } from 'lucide-react';
import styles from './WelcomeScreen.module.css';

export interface WelcomeScreenProps {
  onQuestionClick: (question: string) => void;
}

const suggestedQuestions = [
  {
    icon: <Calendar size={20} />,
    question: 'Wann wurde Mainz 05 gegründet?',
    category: 'Geschichte',
  },
  {
    icon: <Trophy size={20} />,
    question: 'Wer ist der beste Torschütze aller Zeiten?',
    category: 'Rekorde',
  },
  {
    icon: <Users size={20} />,
    question: 'Welche Spieler wurden später Trainer?',
    category: 'Personen',
  },
  {
    icon: <History size={20} />,
    question: 'Wann war der erste Bundesliga-Aufstieg?',
    category: 'Meilensteine',
  },
  {
    icon: <Sparkles size={20} />,
    question: 'Was bedeutet der Karnevalsverein?',
    category: 'Kultur',
  },
  {
    icon: <MessageCircle size={20} />,
    question: 'Erzähl mir über Jürgen Klopp',
    category: 'Legenden',
  },
];

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onQuestionClick }) => {
  return (
    <div className={styles.container}>
      <div className={styles.hero}>
        <div className={styles.iconWrapper}>
          <div className={styles.stadiumIcon}>
            <svg
              viewBox="0 0 64 64"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className={styles.stadiumSvg}
            >
              <rect x="8" y="24" width="48" height="24" rx="2" fill="currentColor" opacity="0.2" />
              <rect x="12" y="20" width="4" height="28" rx="1" fill="currentColor" />
              <rect x="20" y="20" width="4" height="28" rx="1" fill="currentColor" />
              <rect x="28" y="20" width="4" height="28" rx="1" fill="currentColor" />
              <rect x="36" y="20" width="4" height="28" rx="1" fill="currentColor" />
              <rect x="44" y="20" width="4" height="28" rx="1" fill="currentColor" />
              <rect x="52" y="20" width="4" height="28" rx="1" fill="currentColor" />
              <ellipse cx="32" cy="36" rx="16" ry="8" fill="currentColor" opacity="0.3" />
            </svg>
          </div>
        </div>

        <h1 className={styles.title}>Mainz 05 Assistent</h1>
        <p className={styles.subtitle}>
          Dein Experte für die Geschichte und Rekorde von Mainz 05
        </p>
      </div>

      <div className={styles.divider}>
        <span className={styles.dividerText}>Beliebte Fragen</span>
      </div>

      <div className={styles.suggestions}>
        {suggestedQuestions.map((item, index) => (
          <button
            key={index}
            className={styles.suggestionCard}
            onClick={() => onQuestionClick(item.question)}
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            <div className={styles.suggestionIcon}>{item.icon}</div>
            <div className={styles.suggestionContent}>
              <span className={styles.suggestionCategory}>{item.category}</span>
              <span className={styles.suggestionQuestion}>{item.question}</span>
            </div>
          </button>
        ))}
      </div>

      <div className={styles.footer}>
        <p className={styles.footerText}>
          Stelle eine Frage oder wähle eine der Vorschläge aus
        </p>
      </div>
    </div>
  );
};
