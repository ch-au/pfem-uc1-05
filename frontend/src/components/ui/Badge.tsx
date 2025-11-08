import React from 'react';
import { clsx } from 'clsx';
import styles from './Badge.module.css';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'error' | 'warning' | 'info';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  className,
  ...props
}) => {
  return (
    <span
      className={clsx(styles.badge, styles[`badge--${variant}`], className)}
      {...props}
    >
      {children}
    </span>
  );
};



