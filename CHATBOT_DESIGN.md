# Chatbot Window Component - Design Specification
## Mainz 05 Edition

---

## 1. Design Philosophy

### Brand Identity: Mainz 05
The chatbot window embodies the spirit of FSV Mainz 05:
- **Colors**: Dominant Mainz Red (#C8191E) with clean white (#FFFFFF) backgrounds
- **Typography**: Clear, modern sans-serif fonts for accessibility
- **Personality**: Professional yet approachable, knowledgeable yet humble
- **Energy**: Dynamic with subtle animations that feel lively without being distracting

### Design Principles
1. **Clarity First**: Every interaction should be immediately understandable
2. **Performance**: Smooth, responsive animations at 60fps
3. **Accessibility**: WCAG 2.1 AA compliant, keyboard navigable
4. **Progressive Enhancement**: Core functionality works, enhancements delight
5. **Mobile-First**: Optimized for mobile, enhanced for desktop

---

## 2. Component Architecture

### Component Hierarchy
```
ChatbotWindow (new enhanced version)
├── ChatHeader
│   ├── TeamBranding
│   ├── StatusIndicator
│   └── ActionMenu
├── ChatMessages
│   ├── WelcomeScreen (empty state)
│   ├── MessageList
│   │   ├── UserMessage
│   │   ├── BotMessage
│   │   │   ├── MessageContent
│   │   │   ├── Sources (collapsible)
│   │   │   └── FeedbackButtons
│   │   └── SystemMessage
│   ├── TypingIndicator
│   └── ScrollToBottom
└── ChatInputArea
    ├── SuggestedQuestions (chips)
    ├── TextInput (auto-resize)
    └── SendButton
```

### State Management
Using Zustand store pattern:
```typescript
interface ChatbotWindowStore {
  // Session management
  sessionId: string | null;
  isConnected: boolean;

  // Messages
  messages: EnhancedChatMessage[];
  pendingMessage: string;

  // UI state
  isLoading: boolean;
  typingIndicatorVisible: boolean;
  showSuggestions: boolean;
  scrollPosition: 'bottom' | 'scrolled';

  // User preferences
  soundEnabled: boolean;
  animationsEnabled: boolean;

  // Analytics
  messageCount: number;
  sessionStartTime: Date;
}
```

---

## 3. Visual Design Specifications

### Color Palette
```css
/* Primary Colors - Mainz 05 */
--mainz-red: #C8191E;           /* Primary brand color */
--mainz-red-dark: #A01418;      /* Hover states, depth */
--mainz-red-light: #E53E3E;     /* Accents, highlights */
--mainz-white: #FFFFFF;         /* Background, text on red */

/* Neutrals */
--gray-50: #F9FAFB;             /* Page background */
--gray-100: #F3F4F6;            /* Chat background gradient */
--gray-200: #E5E7EB;            /* Borders */
--gray-400: #9CA3AF;            /* Disabled text */
--gray-600: #6B7280;            /* Secondary text */
--gray-800: #374151;            /* Primary text */

/* Semantic Colors */
--success: #10B981;             /* Success states */
--warning: #F59E0B;             /* Warning states */
--error: #EF4444;               /* Error states */
--info: #3B82F6;                /* Info states */

/* Gradients */
--gradient-red: linear-gradient(135deg, #C8191E 0%, #A01418 100%);
--gradient-bg: linear-gradient(to bottom, #F9FAFB, #F3F4F6);
--gradient-shine: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 100%);
```

### Typography Scale
```css
/* Font Families */
--font-primary: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
--font-mono: 'Monaco', 'Courier New', monospace;

/* Font Sizes */
--text-xs: 0.6875rem;    /* 11px - timestamps */
--text-sm: 0.8125rem;    /* 13px - small UI */
--text-base: 0.9375rem;  /* 15px - body text */
--text-lg: 1.125rem;     /* 18px - headings */
--text-xl: 1.5rem;       /* 24px - titles */

/* Font Weights */
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;

/* Line Heights */
--leading-tight: 1.4;
--leading-normal: 1.6;
--leading-relaxed: 1.8;
```

### Spacing System
```css
/* Consistent spacing scale (8px base) */
--space-xs: 0.25rem;   /* 4px */
--space-sm: 0.5rem;    /* 8px */
--space-md: 0.75rem;   /* 12px */
--space-lg: 1rem;      /* 16px */
--space-xl: 1.5rem;    /* 24px */
--space-2xl: 2rem;     /* 32px */
--space-3xl: 3rem;     /* 48px */
```

### Border Radius
```css
--radius-sm: 0.375rem;   /* 6px - small elements */
--radius-md: 0.75rem;    /* 12px - cards, inputs */
--radius-lg: 1rem;       /* 16px - containers */
--radius-xl: 1.25rem;    /* 20px - message bubbles */
--radius-full: 9999px;   /* circular elements */
```

### Shadows
```css
/* Elevation system */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
--shadow-md: 0 2px 8px rgba(0, 0, 0, 0.08);
--shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.12);
--shadow-xl: 0 8px 24px rgba(0, 0, 0, 0.16);

/* Mainz Red shadows for brand elements */
--shadow-red: 0 4px 12px rgba(200, 25, 30, 0.25);
--shadow-red-lg: 0 8px 24px rgba(200, 25, 30, 0.35);
```

---

## 4. Component Details

### 4.1 ChatHeader
**Purpose**: Brand identity, status indication, quick actions

**Visual Design**:
```
┌─────────────────────────────────────────────────────┐
│  🔴 Mainz 05 Chat    ●Online      [⋮]               │
└─────────────────────────────────────────────────────┘
```

**Features**:
- Mainz 05 logo/wordmark with subtle shine effect
- Real-time connection status indicator
  - Green dot: Connected
  - Yellow dot: Connecting
  - Red dot: Disconnected
- Action menu (kebab menu):
  - Clear conversation
  - Export chat history
  - Settings (sound, animations)
  - Help & feedback

**Technical Details**:
- Fixed height: 64px
- Background: White with subtle bottom border
- Sticky positioning during scroll
- Smooth color transitions for status changes

### 4.2 WelcomeScreen (Empty State)
**Purpose**: Engaging first impression, guided onboarding

**Visual Design**:
```
        ╔══════════════════════════════╗
        ║    🏟️  Mainz 05 Assistant   ║
        ║                              ║
        ║  Dein Experte für die        ║
        ║  Geschichte von Mainz 05     ║
        ╚══════════════════════════════╝

        Beliebte Fragen:
        ┌──────────────────────────────┐
        │ 📜 Vereinsgeschichte         │
        └──────────────────────────────┘
        ┌──────────────────────────────┐
        │ 🏆 Erfolge & Titel           │
        └──────────────────────────────┘
        ┌──────────────────────────────┐
        │ ⚽ Legendäre Spieler         │
        └──────────────────────────────┘
```

**Features**:
- Animated entry (fade + scale)
- Stadium/crest illustration (SVG)
- 4-6 suggested question chips
- Subtle pulsing animation on chips
- Responsive grid layout

**Suggested Questions**:
1. "Wann wurde Mainz 05 gegründet?"
2. "Wer ist der beste Torschütze aller Zeiten?"
3. "Welche Spieler wurden später Trainer?"
4. "Wann war der erste Bundesliga-Aufstieg?"
5. "Was bedeutet der Karnevalsverein?"
6. "Erzähl mir über Jürgen Klopp"

### 4.3 Message Bubbles

#### User Message
```
                    ┌──────────────────────┐
                    │ Wer ist der beste    │
                    │ Torschütze?          │
                    └──────────────────────┘
                              👤
                           14:23
```

**Style**:
- Background: Mainz Red gradient
- Color: White text
- Alignment: Right
- Border radius: 1.25rem (bottom-right: 0.375rem)
- Shadow: Red glow shadow
- Max width: 75%
- Animation: Slide in from right + fade

#### Bot Message
```
🤖                  ┌──────────────────────┐
                    │ Mohamed Zidan ist    │
14:23               │ mit 64 Toren...      │
                    │                      │
                    │ [Quellen anzeigen ▼] │
                    │                      │
                    │        👍  👎        │
                    └──────────────────────┘
```

**Style**:
- Background: White
- Color: Dark gray text
- Alignment: Left
- Border: 1px light gray
- Border radius: 1.25rem (bottom-left: 0.375rem)
- Shadow: Subtle elevation
- Max width: 75%
- Animation: Slide in from left + fade

**Enhanced Features**:
- Collapsible sources section showing:
  - SQL query (formatted, syntax highlighted)
  - Table name
  - Confidence score
- Feedback buttons (thumbs up/down)
- Copy button for message content
- Markdown rendering support:
  - Bold, italic, links
  - Code blocks with syntax highlighting
  - Lists (bullet, numbered)

#### System Message
```
        ┌────────────────────────────┐
        │ ℹ️ Neue Session gestartet  │
        └────────────────────────────┘
```

**Style**:
- Background: Light gray
- Color: Medium gray
- Alignment: Center
- Smaller font size
- Monospace font
- Subtle appearance

### 4.4 TypingIndicator
**Visual Design**:
```
🤖  ●●● Schreibt...
```

**Animation**:
- Three dots with sequential bounce
- Smooth easing (cubic-bezier)
- 1.2s loop duration
- Fades in/out smoothly

**Implementation**:
```css
@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}

.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
```

### 4.5 ChatInputArea
```
┌────────────────────────────────────────────────┐
│ 💬 Stelle eine Frage zu Mainz 05...      [📤] │
└────────────────────────────────────────────────┘

  [📜 Geschichte] [🏆 Erfolge] [⚽ Spieler]
```

**Features**:
- Auto-resizing textarea (1-5 lines)
- Character counter (appears at 200+ chars, max 500)
- Send button states:
  - Disabled: Gray, no interaction
  - Ready: Mainz Red, hover effect
  - Sending: Loading spinner
- Keyboard shortcuts:
  - Enter: Send message
  - Shift+Enter: New line
  - Escape: Clear input
- Suggested question chips (contextual)
- Voice input button (future enhancement)

**Accessibility**:
- Proper ARIA labels
- Focus management
- Screen reader announcements
- Keyboard navigation

---

## 5. Animations & Transitions

### Animation Philosophy
- **Purpose-driven**: Every animation serves UX purpose
- **Performant**: Use transform/opacity for 60fps
- **Subtle**: Natural, not distracting
- **Responsive**: Reduced motion support

### Key Animations

#### Message Entry
```css
@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.message {
  animation: messageSlideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

#### Hover Effects
```css
.messageBubble {
  transition: all 0.2s ease;
}

.messageBubble:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}
```

#### Button Press
```css
.button:active {
  transform: scale(0.95);
  transition: transform 0.1s;
}
```

#### Scroll to Bottom Button
```css
@keyframes floatUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.scrollButton {
  animation: floatUp 0.3s ease-out;
}
```

### Reduced Motion Support
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 6. Responsive Design

### Breakpoints
```css
/* Mobile first approach */
--mobile: 0px;        /* Default */
--tablet: 640px;      /* sm */
--desktop: 1024px;    /* lg */
--wide: 1280px;       /* xl */
```

### Layout Adaptations

#### Mobile (< 640px)
- Full viewport height
- Single column layout
- Simplified header (no text labels)
- Floating send button (icon only)
- Message max-width: 85%
- Bottom navigation spacing
- Touch-optimized tap targets (min 44x44px)

#### Tablet (640px - 1024px)
- Card-based layout with margins
- Dual column possible for landscape
- Full button labels visible
- Message max-width: 80%

#### Desktop (> 1024px)
- Centered card (max-width: 800px)
- Enhanced hover states
- Keyboard shortcuts visible
- Message max-width: 75%
- Sidebar navigation visible

---

## 7. Enhanced Features

### 7.1 Source Display
When bot answers include database queries:

```
┌─────────────────────────────────────────────┐
│ 📊 Quellen (Vertrauenswürdigkeit: 95%)     │
│                                             │
│ Tabelle: player_stats                      │
│ SQL-Abfrage:                                │
│ ┌─────────────────────────────────────────┐ │
│ │ SELECT player_name, total_goals         │ │
│ │ FROM player_stats                       │ │
│ │ ORDER BY total_goals DESC               │ │
│ │ LIMIT 1;                                │ │
│ └─────────────────────────────────────────┘ │
│                                      [Copy] │
└─────────────────────────────────────────────┘
```

**Features**:
- Collapsible section (default: collapsed)
- Syntax-highlighted SQL
- Confidence score visualization
- Copy button for SQL query
- Table schema link (tooltip)

### 7.2 Feedback System
```
Helpful?  👍 (123)    👎 (5)
```

**Implementation**:
- Optimistic UI updates
- Visual feedback on click
- Aggregate counts visible
- Optional feedback form on negative rating
- Analytics tracking

### 7.3 Message Actions
Hover over bot message reveals:
```
[📋 Copy]  [🔊 Read aloud]  [🔗 Share]
```

### 7.4 Scroll Behavior
- Auto-scroll on new message (if at bottom)
- Preserve scroll position when not at bottom
- "New messages" badge when scrolled up
- Smooth scroll to bottom button
- Infinite scroll for history (future)

### 7.5 Loading States
1. **Initial Connection**: Skeleton screen
2. **Sending Message**: Pulsing user bubble
3. **Waiting for Response**: Typing indicator
4. **Error State**: Retry button with error message

---

## 8. Accessibility (A11y)

### WCAG 2.1 AA Compliance

#### Color Contrast
- Text on white: 7:1 (AAA)
- Text on Mainz Red: 4.5:1 (AA)
- UI elements: 3:1 minimum

#### Keyboard Navigation
```
Tab:         Next interactive element
Shift+Tab:   Previous element
Enter:       Activate button
Space:       Toggle checkbox
Escape:      Close modal/clear input
↑/↓:         Navigate message history (future)
Ctrl+/:      Show keyboard shortcuts
```

#### Screen Reader Support
```html
<div role="log" aria-live="polite" aria-atomic="false">
  <!-- Messages appear here with announcements -->
</div>

<button aria-label="Send message" aria-disabled="true">
  <svg aria-hidden="true">...</svg>
</button>

<div aria-label="Bot is typing" role="status">
  <span class="visually-hidden">Assistant is typing</span>
</div>
```

#### Focus Management
- Visible focus indicators (2px Mainz Red outline)
- Focus trap in modals
- Return focus after actions
- Skip to content link

---

## 9. Performance Optimization

### Rendering Strategy
1. **Virtualization**: Long message lists (react-window)
2. **Lazy Loading**: Images and media
3. **Debouncing**: Input events (300ms)
4. **Memoization**: Expensive computations
5. **Code Splitting**: Route-based chunks

### Animation Performance
```css
/* Use GPU-accelerated properties */
.message {
  will-change: transform, opacity;
  transform: translateZ(0); /* Force GPU layer */
}
```

### Bundle Size
- Tree-shaking for unused code
- Dynamic imports for heavy features
- SVG optimization
- Font subsetting (if custom fonts)
- Target: < 50KB gzipped for chat bundle

---

## 10. Error Handling

### Error Types & Messages

#### Network Error
```
┌──────────────────────────────────────┐
│ ⚠️ Verbindung unterbrochen           │
│                                      │
│ Prüfe deine Internetverbindung       │
│                                      │
│        [Erneut versuchen]            │
└──────────────────────────────────────┘
```

#### API Error
```
┌──────────────────────────────────────┐
│ ❌ Nachricht konnte nicht            │
│    gesendet werden                   │
│                                      │
│ [Erneut senden] [Details]            │
└──────────────────────────────────────┘
```

#### Rate Limit
```
┌──────────────────────────────────────┐
│ ⏱️ Zu viele Anfragen                 │
│                                      │
│ Bitte warte 30 Sekunden              │
│                                      │
│ Nächste Anfrage in: 0:29            │
└──────────────────────────────────────┘
```

### Error Recovery
- Automatic retry with exponential backoff
- Offline queue for messages
- Session restoration on reconnect
- Clear error messaging
- Fallback UI for critical failures

---

## 11. Technical Implementation

### Component Structure

```typescript
// ChatbotWindow.tsx
import React, { useEffect, useRef } from 'react';
import { ChatHeader } from './ChatHeader';
import { WelcomeScreen } from './WelcomeScreen';
import { MessageList } from './MessageList';
import { TypingIndicator } from './TypingIndicator';
import { ChatInputArea } from './ChatInputArea';
import { ScrollToBottomButton } from './ScrollToBottomButton';
import { useChatbotWindow } from '../../hooks/useChatbotWindow';
import styles from './ChatbotWindow.module.css';

export const ChatbotWindow: React.FC = () => {
  const {
    messages,
    isLoading,
    isConnected,
    showWelcome,
    showScrollButton,
    sendMessage,
    scrollToBottom,
  } = useChatbotWindow();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  return (
    <div className={styles.chatbotWindow}>
      <ChatHeader isConnected={isConnected} />

      <div className={styles.messagesContainer}>
        {showWelcome ? (
          <WelcomeScreen onQuestionClick={sendMessage} />
        ) : (
          <>
            <MessageList messages={messages} />
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </>
        )}

        {showScrollButton && (
          <ScrollToBottomButton onClick={scrollToBottom} />
        )}
      </div>

      <ChatInputArea
        onSend={sendMessage}
        isLoading={isLoading}
        disabled={!isConnected}
      />
    </div>
  );
};
```

### Custom Hook

```typescript
// hooks/useChatbotWindow.ts
import { useEffect, useState, useCallback } from 'react';
import { useChatStore } from '../store/chatStore';
import { chatService } from '../services/chatService';

export const useChatbotWindow = () => {
  const {
    sessionId,
    messages,
    isLoading,
    error,
    setSessionId,
    addMessage,
    setLoading,
  } = useChatStore();

  const [isConnected, setIsConnected] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Initialize session
  useEffect(() => {
    initializeSession();
  }, []);

  const initializeSession = async () => {
    try {
      const newSessionId = await chatService.createSession();
      setSessionId(newSessionId);
      setIsConnected(true);
    } catch (error) {
      console.error('Failed to initialize session:', error);
      setIsConnected(false);
    }
  };

  const sendMessage = useCallback(async (content: string) => {
    if (!sessionId || isLoading) return;

    const userMessage = {
      role: 'user' as const,
      content,
      timestamp: new Date().toISOString(),
    };

    addMessage(userMessage);
    setLoading(true);

    try {
      const response = await chatService.sendMessage(sessionId, content);

      const assistantMessage = {
        role: 'assistant' as const,
        content: response.answer,
        timestamp: new Date().toISOString(),
        metadata: {
          sources: response.sources,
          confidence: response.confidence,
          sql_query: response.sql_query,
        },
      };

      addMessage(assistantMessage);
    } catch (error) {
      const errorMessage = {
        role: 'error' as const,
        content: 'Entschuldigung, es ist ein Fehler aufgetreten.',
        timestamp: new Date().toISOString(),
      };
      addMessage(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [sessionId, isLoading, addMessage, setLoading]);

  return {
    messages,
    isLoading,
    isConnected,
    error,
    showWelcome: messages.length === 0,
    showScrollButton,
    sendMessage,
    scrollToBottom: () => {
      // Scroll implementation
    },
  };
};
```

---

## 12. Testing Strategy

### Unit Tests
- Individual component rendering
- State management logic
- Utility functions
- Message formatting

### Integration Tests
- Complete message flow
- Error handling
- Session management
- API integration

### E2E Tests (Playwright)
```typescript
test('user can send message and receive response', async ({ page }) => {
  await page.goto('/');

  // Type message
  await page.fill('[aria-label="Message input"]', 'Wer ist der beste Torschütze?');

  // Send message
  await page.click('[aria-label="Send message"]');

  // Wait for response
  await page.waitForSelector('[data-message-role="assistant"]');

  // Verify response
  const response = await page.textContent('[data-message-role="assistant"]');
  expect(response).toContain('Zidan');
});
```

### Accessibility Tests
- Axe-core integration
- Keyboard navigation testing
- Screen reader testing (manual)
- Color contrast validation

### Performance Tests
- Lighthouse CI
- Bundle size monitoring
- Runtime performance profiling
- Memory leak detection

---

## 13. Future Enhancements

### Phase 2 Features
1. **Voice Input/Output**: Web Speech API integration
2. **Multi-language**: i18n support (German, English)
3. **Rich Media**: Image, video, audio responses
4. **Code Blocks**: Syntax highlighting for technical responses
5. **Attachments**: File upload support
6. **Reactions**: Quick emoji reactions to messages
7. **Search**: Full-text search in conversation history
8. **Themes**: Light/dark mode toggle

### Phase 3 Features
1. **Conversation Branches**: Explore alternative answers
2. **Sharing**: Share conversations via link
3. **Export**: Download as PDF, Markdown, JSON
4. **Smart Suggestions**: ML-powered question suggestions
5. **Persistence**: Local storage + sync
6. **Analytics Dashboard**: Usage insights for admins
7. **Custom Avatars**: Personalization options
8. **Integrations**: Calendar, tickets, news

---

## 14. Success Metrics

### Primary KPIs
1. **User Engagement**
   - Messages per session: Target > 5
   - Session duration: Target > 3 minutes
   - Return rate: Target > 40%

2. **Performance**
   - First Contentful Paint: < 1.5s
   - Time to Interactive: < 3s
   - Largest Contentful Paint: < 2.5s

3. **Satisfaction**
   - Thumbs up rate: Target > 80%
   - Error rate: Target < 2%
   - Task completion: Target > 90%

### Secondary Metrics
- Average response time
- Questions per unique user
- Most asked questions
- Mobile vs desktop usage
- Accessibility score (Lighthouse)

---

## 15. Implementation Checklist

### Phase 1: Core Components ✓
- [ ] ChatbotWindow shell structure
- [ ] ChatHeader with branding
- [ ] WelcomeScreen with suggestions
- [ ] Enhanced MessageList
- [ ] UserMessage bubble
- [ ] BotMessage bubble with sources
- [ ] TypingIndicator animation
- [ ] ChatInputArea with auto-resize
- [ ] Basic styling (CSS Modules)

### Phase 2: Interactivity
- [ ] useChatbotWindow hook
- [ ] Message sending flow
- [ ] Error handling UI
- [ ] Loading states
- [ ] Scroll management
- [ ] ScrollToBottom button
- [ ] Keyboard shortcuts
- [ ] Responsive layouts

### Phase 3: Polish
- [ ] Animations & transitions
- [ ] Accessibility features
- [ ] Feedback system
- [ ] Source collapsible
- [ ] Message actions (copy, etc.)
- [ ] Sound effects (optional)
- [ ] Performance optimization
- [ ] Cross-browser testing

### Phase 4: Testing & Launch
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests
- [ ] E2E tests
- [ ] Accessibility audit
- [ ] Performance audit
- [ ] User acceptance testing
- [ ] Documentation
- [ ] Deployment

---

## Conclusion

This design creates a sophisticated, polished chatbot experience that embodies the Mainz 05 brand while prioritizing usability, performance, and accessibility. The component architecture is modular and extensible, allowing for future enhancements while maintaining a clean, maintainable codebase.

**Core Design Tenets**:
1. **Brand-First**: Every pixel reinforces Mainz 05 identity
2. **User-Centric**: Intuitive, accessible, delightful
3. **Performance**: Fast, smooth, responsive
4. **Future-Proof**: Extensible, testable, documented

Let's build something fans will love! ⚽🔴⚪
