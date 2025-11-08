import React from 'react';
import { clsx } from 'clsx';
import styles from './IconButton.module.css';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
}

export const IconButton: React.FC<IconButtonProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className,
  ...props
}) => {
  return (
    <button
      className={clsx(
        styles.iconButton,
        styles[`iconButton--${variant}`],
        styles[`iconButton--${size}`],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
};



