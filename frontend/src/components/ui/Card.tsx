import React from 'react';
import { clsx } from 'clsx';
import styles from './Card.module.css';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'interactive';
  padding?: 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  padding = 'md',
  className,
  ...props
}) => {
  return (
    <div
      className={clsx(
        styles.card,
        styles[`card--${variant}`],
        styles[`card--padding-${padding}`],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};



