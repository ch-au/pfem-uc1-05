import React, { useState } from 'react';
import { MoreVertical, X, Download, Settings, HelpCircle, Trash2 } from 'lucide-react';
import { IconButton } from '../ui/IconButton';
import styles from './ChatHeader.module.css';

export interface ChatHeaderProps {
  isConnected?: boolean;
  onClearChat?: () => void;
  onExportChat?: () => void;
  onOpenSettings?: () => void;
  onOpenHelp?: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  isConnected = true,
  onClearChat,
  onExportChat,
  onOpenSettings,
  onOpenHelp,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);

  const getStatusLabel = () => {
    if (isConnected) return 'Online';
    return 'Offline';
  };

  const getStatusClass = () => {
    if (isConnected) return styles.statusOnline;
    return styles.statusOffline;
  };

  const handleMenuItemClick = (action?: () => void) => {
    setMenuOpen(false);
    action?.();
  };

  return (
    <header className={styles.header}>
      <div className={styles.branding}>
        <div className={styles.logoContainer}>
          <div className={styles.logo}>
            <span className={styles.logoText}>Mainz 05</span>
          </div>
        </div>
        <div className={styles.title}>
          <h1 className={styles.titleText}>Chat</h1>
        </div>
      </div>

      <div className={styles.controls}>
        <div className={styles.status}>
          <span className={`${styles.statusDot} ${getStatusClass()}`} />
          <span className={styles.statusLabel}>{getStatusLabel()}</span>
        </div>

        <div className={styles.menuContainer}>
          <IconButton
            icon={menuOpen ? <X size={20} /> : <MoreVertical size={20} />}
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Menu"
            className={styles.menuButton}
          />

          {menuOpen && (
            <div className={styles.menu}>
              <button
                className={styles.menuItem}
                onClick={() => handleMenuItemClick(onClearChat)}
              >
                <Trash2 size={16} />
                <span>Unterhaltung löschen</span>
              </button>
              <button
                className={styles.menuItem}
                onClick={() => handleMenuItemClick(onExportChat)}
              >
                <Download size={16} />
                <span>Chat exportieren</span>
              </button>
              <button
                className={styles.menuItem}
                onClick={() => handleMenuItemClick(onOpenSettings)}
              >
                <Settings size={16} />
                <span>Einstellungen</span>
              </button>
              <button
                className={styles.menuItem}
                onClick={() => handleMenuItemClick(onOpenHelp)}
              >
                <HelpCircle size={16} />
                <span>Hilfe & Feedback</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
