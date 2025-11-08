import React from 'react';
import { Play } from 'lucide-react';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import styles from './QuizCard.module.css';

export interface QuizCardProps {
  title: string;
  subtitle?: string;
  metadata?: Array<{ label: string; value: string }>;
  questionCount?: number;
  onClick?: () => void;
  variant?: 'featured' | 'default';
}

export const QuizCard: React.FC<QuizCardProps> = ({
  title,
  subtitle,
  metadata,
  questionCount,
  onClick,
  variant = 'default',
}) => {
  if (variant === 'featured') {
    return (
      <div className={styles.featuredCard}>
        <div className={styles.featuredContent}>
          <h3 className={styles.featuredTitle}>{title}</h3>
          {subtitle && <p className={styles.featuredSubtitle}>{subtitle}</p>}
          <div className={styles.featuredMeta}>
            {metadata?.map((item, index) => (
              <div key={index} className={styles.metaItem}>
                <span className={styles.metaLabel}>{item.label}</span>
                {item.value && <span className={styles.metaValue}>{item.value}</span>}
              </div>
            ))}
            {questionCount && <Badge variant="info">{questionCount} Fragen</Badge>}
          </div>
          <Button
            variant="secondary"
            size="lg"
            icon={<Play size={20} />}
            onClick={onClick}
            className={styles.playButton}
          >
            Jetzt spielen
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.card} onClick={onClick}>
      <div className={styles.icon}>05</div>
      <h4 className={styles.title}>{title}</h4>
      {questionCount && <p className={styles.count}>{questionCount} Fragen</p>}
    </div>
  );
};



