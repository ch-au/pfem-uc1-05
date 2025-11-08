import React, { useRef, useEffect } from 'react';
import { ChatHeader } from './ChatHeader';
import { WelcomeScreen } from './WelcomeScreen';
import { ChatMessageComponent } from './ChatMessage';
import { BotMessage } from './BotMessage';
import { TypingIndicator } from './TypingIndicator';
import { ChatInput } from './ChatInput';
import { ScrollToBottomButton } from './ScrollToBottomButton';
import { SuggestionChips } from './SuggestionChips';
import { useChatbotWindow } from '../../hooks/useChatbotWindow';
import styles from './ChatbotWindow.module.css';

const contextualSuggestions: string[] = [
  'Mehr über die Vereinsgeschichte',
  'Legendäre Spieler',
  'Größte Erfolge',
];

export const ChatbotWindow: React.FC = () => {
  const {
    messages,
    isLoading,
    isConnected,
    error,
    showWelcome,
    showScrollButton,
    sendMessage,
    scrollToBottom,
    clearChat,
    handleFeedback,
  } = useChatbotWindow();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (containerRef.current) {
      const { scrollHeight, clientHeight, scrollTop } = containerRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;

      if (isNearBottom) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
    }
  }, [messages, isLoading]);

  const handleClearChat = () => {
    if (window.confirm('Möchtest du die gesamte Unterhaltung löschen?')) {
      clearChat();
    }
  };

  const handleExportChat = () => {
    const chatText = messages
      .map((msg) => {
        const time = msg.timestamp
          ? new Date(msg.timestamp).toLocaleString('de-DE')
          : '';
        return `[${time}] ${msg.role}: ${msg.content}`;
      })
      .join('\n\n');

    const blob = new Blob([chatText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mainz05-chat-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleOpenSettings = () => {
    alert('Einstellungen werden in einer zukünftigen Version verfügbar sein.');
  };

  const handleOpenHelp = () => {
    alert('Hilfe & Feedback werden in einer zukünftigen Version verfügbar sein.');
  };

  return (
    <div className={styles.chatbotWindow}>
      <ChatHeader
        isConnected={isConnected}
        onClearChat={handleClearChat}
        onExportChat={handleExportChat}
        onOpenSettings={handleOpenSettings}
        onOpenHelp={handleOpenHelp}
      />

      <div ref={containerRef} className={styles.messagesContainer}>
        {showWelcome ? (
          <WelcomeScreen onQuestionClick={sendMessage} />
        ) : (
          <div className={styles.messagesList}>
            {messages.map((message, index) => {
              if (message.role === 'assistant') {
                return (
                  <BotMessage
                    key={index}
                    message={message}
                    onFeedback={handleFeedback}
                  />
                );
              }
              return <ChatMessageComponent key={index} message={message} />;
            })}

            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}

        {showScrollButton && <ScrollToBottomButton onClick={scrollToBottom} />}
      </div>

      <div className={styles.inputContainer}>
        {!showWelcome && messages.length > 0 && (
          <SuggestionChips
            suggestions={contextualSuggestions}
            onSelect={sendMessage}
            maxVisible={3}
          />
        )}
        <ChatInput
          onSend={sendMessage}
          isLoading={isLoading}
          disabled={!isConnected}
        />
      </div>

      {error && (
        <div className={styles.errorBanner}>
          <span className={styles.errorText}>{error}</span>
        </div>
      )}
    </div>
  );
};
