import React from 'react';
import { clsx } from 'clsx';
import styles from './Avatar.module.css';

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'user' | 'bot';
  size?: 'sm' | 'md' | 'lg';
  online?: boolean;
  children?: React.ReactNode;
}

export const Avatar: React.FC<AvatarProps> = ({
  variant = 'user',
  size = 'md',
  online,
  children,
  className,
  ...props
}) => {
  return (
    <div
      className={clsx(
        styles.avatar,
        styles[`avatar--${variant}`],
        styles[`avatar--${size}`],
        className
      )}
      {...props}
    >
      {children || (variant === 'bot' ? '05' : <UserIcon />)}
      {online !== undefined && (
        <span
          className={clsx(
            styles.status,
            online ? styles['status--online'] : styles['status--offline']
          )}
        />
      )}
    </div>
  );
};

const UserIcon: React.FC = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);



