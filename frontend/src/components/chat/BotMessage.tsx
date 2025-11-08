import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Copy, ThumbsUp, ThumbsDown, Database } from 'lucide-react';
import { Avatar } from '../ui/Avatar';
import { IconButton } from '../ui/IconButton';
import type { ChatMessage } from '../../types/api';
import styles from './BotMessage.module.css';

export interface BotMessageProps {
  message: ChatMessage;
  onFeedback?: (messageId: string, feedback: 'positive' | 'negative') => void;
}

export const BotMessage: React.FC<BotMessageProps> = ({ message, onFeedback }) => {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<'positive' | 'negative' | null>(null);
  const [copiedSQL, setCopiedSQL] = useState(false);

  const { content, timestamp, metadata } = message;
  const sources = metadata?.sources as Array<{ sql?: string; table?: string }> | undefined;
  const confidence = metadata?.confidence as number | undefined;
  const sqlQuery = metadata?.sql_query as string | undefined;

  const hasSources = sources && sources.length > 0;
  const hasSQL = !!sqlQuery;

  const formatTime = (timestamp?: string) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  };

  const handleFeedback = (type: 'positive' | 'negative') => {
    setFeedbackGiven(type);
    onFeedback?.(timestamp || '', type);
  };

  const copySQL = async () => {
    if (sqlQuery) {
      await navigator.clipboard.writeText(sqlQuery);
      setCopiedSQL(true);
      setTimeout(() => setCopiedSQL(false), 2000);
    }
  };

  const getConfidenceColor = (score?: number) => {
    if (!score) return '#9CA3AF';
    if (score >= 0.8) return '#10B981';
    if (score >= 0.5) return '#F59E0B';
    return '#EF4444';
  };

  const getConfidenceLabel = (score?: number) => {
    if (!score) return 'Unbekannt';
    if (score >= 0.8) return 'Hoch';
    if (score >= 0.5) return 'Mittel';
    return 'Niedrig';
  };

  return (
    <div className={styles.message}>
      <Avatar variant="bot" size="md" />

      <div className={styles.content}>
        <div className={styles.bubble}>
          <div className={styles.text}>{content}</div>

          {(hasSources || hasSQL) && (
            <div className={styles.sourcesSection}>
              <button
                className={styles.sourcesToggle}
                onClick={() => setSourcesExpanded(!sourcesExpanded)}
              >
                <Database size={16} />
                <span>Quellen anzeigen</span>
                {confidence !== undefined && (
                  <span
                    className={styles.confidenceBadge}
                    style={{ color: getConfidenceColor(confidence) }}
                  >
                    {getConfidenceLabel(confidence)}: {Math.round(confidence * 100)}%
                  </span>
                )}
                {sourcesExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              {sourcesExpanded && (
                <div className={styles.sourcesContent}>
                  {hasSQL && (
                    <div className={styles.sqlSection}>
                      <div className={styles.sqlHeader}>
                        <span className={styles.sqlLabel}>SQL-Abfrage:</span>
                        <button
                          className={styles.copyButton}
                          onClick={copySQL}
                          title="SQL kopieren"
                        >
                          <Copy size={14} />
                          <span>{copiedSQL ? 'Kopiert!' : 'Kopieren'}</span>
                        </button>
                      </div>
                      <pre className={styles.sqlCode}>{sqlQuery}</pre>
                    </div>
                  )}

                  {hasSources && (
                    <div className={styles.sourcesList}>
                      {sources.map((source, index) => (
                        <div key={index} className={styles.sourceItem}>
                          {source.table && (
                            <div className={styles.sourceDetail}>
                              <span className={styles.sourceLabel}>Tabelle:</span>
                              <code className={styles.sourceValue}>{source.table}</code>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div className={styles.actions}>
            <span className={styles.timestamp}>{formatTime(timestamp)}</span>
            <div className={styles.feedback}>
              <span className={styles.feedbackLabel}>Hilfreich?</span>
              <IconButton
                icon={<ThumbsUp size={14} />}
                onClick={() => handleFeedback('positive')}
                className={`${styles.feedbackButton} ${
                  feedbackGiven === 'positive' ? styles.feedbackActive : ''
                }`}
                aria-label="Positive Bewertung"
              />
              <IconButton
                icon={<ThumbsDown size={14} />}
                onClick={() => handleFeedback('negative')}
                className={`${styles.feedbackButton} ${
                  feedbackGiven === 'negative' ? styles.feedbackActive : ''
                }`}
                aria-label="Negative Bewertung"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
