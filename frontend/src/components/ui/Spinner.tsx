import React from 'react';
import { Loader2 } from 'lucide-react';
import styles from './Spinner.module.css';

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className }) => {
  return (
    <Loader2 className={`${styles.spinner} ${styles[`spinner--${size}`]} ${className || ''}`} />
  );
};



