import React from 'react';
import { X, AlertCircle, Info, CheckCircle, AlertTriangle } from 'lucide-react';
import styles from './Alert.module.css';

export interface AlertProps {
  variant?: 'error' | 'warning' | 'info' | 'success';
  title?: string;
  message: string;
  onClose?: () => void;
}

const icons = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
  success: CheckCircle,
};

export const Alert: React.FC<AlertProps> = ({
  variant = 'info',
  title,
  message,
  onClose,
}) => {
  const Icon = icons[variant];

  return (
    <div className={`${styles.alert} ${styles[`alert--${variant}`]}`}>
      <div className={styles.alertIcon}>
        <Icon size={20} />
      </div>
      <div className={styles.alertContent}>
        {title && <div className={styles.alertTitle}>{title}</div>}
        <div className={styles.alertMessage}>{message}</div>
      </div>
      {onClose && (
        <button
          className={styles.alertClose}
          onClick={onClose}
          aria-label="Close alert"
        >
          <X size={18} />
        </button>
      )}
    </div>
  );
};
