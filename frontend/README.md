# FSV Mainz 05 Frontend Application

React + TypeScript + Vite frontend for the FSV Mainz 05 interactive database app.

## 🎯 Overview

This is the user-facing web application that provides:
- **AI Chat Interface**: Natural language queries about FSV Mainz 05 history
- **Interactive Quiz Game**: Multiplayer trivia with AI-generated questions
- **Modern UI**: Responsive design with smooth animations and transitions

## 🛠️ Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| **React** | 19.1 | UI framework |
| **TypeScript** | 5.3 | Type safety |
| **Vite** | 6.0 | Build tool & dev server |
| **React Router** | 7.1 | Client-side routing |
| **Zustand** | 5.0 | State management |
| **Axios** | 1.7 | HTTP client |
| **Lucide React** | - | Icon library |

## 🚀 Quick Start

### Prerequisites
- Node.js 20+
- Backend API running on `http://localhost:8000`

### Installation & Development

```bash
# From project root
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Application runs on http://localhost:3000
```

### Environment Variables

Create `.env` in the `frontend/` directory:

```bash
# Backend API URL
VITE_API_URL=http://localhost:8000

# Optional: Enable debug mode
VITE_DEBUG=true
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/           # React components
│   │   ├── chat/            # Chat-specific components
│   │   │   ├── ChatbotWindow.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── WelcomeScreen.tsx
│   │   │   └── SuggestionChips.tsx
│   │   ├── quiz/            # Quiz-specific components
│   │   │   ├── QuizSetup.tsx
│   │   │   ├── QuizQuestion.tsx
│   │   │   ├── QuizOption.tsx
│   │   │   ├── Leaderboard.tsx
│   │   │   ├── QuizHistory.tsx
│   │   │   └── QuizResults.tsx
│   │   ├── layout/          # Layout components
│   │   │   ├── Header.tsx
│   │   │   ├── Navigation.tsx
│   │   │   └── MobileNav.tsx
│   │   └── ui/              # Reusable UI components
│   │       ├── Button.tsx
│   │       ├── Card.tsx
│   │       ├── Input.tsx
│   │       ├── Alert.tsx
│   │       └── Spinner.tsx
│   ├── pages/               # Page components
│   │   ├── ChatPage.tsx     # AI Chat interface
│   │   └── QuizPage.tsx     # Quiz game interface
│   ├── services/            # API & business logic
│   │   ├── api.ts           # Axios configuration
│   │   ├── chatService.ts   # Chat API calls
│   │   └── quizService.ts   # Quiz API calls
│   ├── stores/              # Zustand state stores
│   │   ├── chatStore.ts     # Chat state management
│   │   └── quizStore.ts     # Quiz state management
│   ├── types/               # TypeScript types
│   │   ├── chat.ts          # Chat-related types
│   │   └── quiz.ts          # Quiz-related types
│   ├── utils/               # Utility functions
│   │   ├── formatting.ts    # Date, number formatting
│   │   └── validation.ts    # Form validation
│   ├── styles/              # Global styles
│   │   └── index.css        # Tailwind + custom CSS
│   ├── App.tsx              # Root component
│   ├── main.tsx             # Entry point
│   └── router.tsx           # Route configuration
├── public/                  # Static assets
│   ├── favicon.ico
│   └── og-image.png
├── index.html               # HTML entry point
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript config
├── tailwind.config.js       # Tailwind CSS config
└── package.json             # Dependencies
```

## 📱 Application Features

### 1. Chat Interface (`/`)

**Purpose:** Natural language database querying powered by AI

**Key Features:**
- 🗨️ Session-based conversations
- 💬 Message history with scrollback
- 🎯 Pre-defined suggestion chips
- 📊 SQL query visualization
- ⏱️ Typing indicators
- 🔄 Auto-scroll to new messages
- 📝 Conversation management (delete sessions)

**Main Components:**
- `ChatbotWindow.tsx` - Main chat container
- `ChatMessage.tsx` - Individual message bubbles (user/assistant)
- `ChatInput.tsx` - Message input field with send button
- `WelcomeScreen.tsx` - Initial landing screen
- `SuggestionChips.tsx` - Quick question buttons

**State Management:**
```typescript
// chatStore.ts
interface ChatStore {
  sessions: ChatSession[];
  currentSessionId: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  createSession: () => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
}
```

### 2. Quiz Game (`/quiz`)

**Purpose:** Interactive multiplayer trivia game

**Key Features:**
- 🎮 Multiplayer support (1-10 players)
- 🎯 6 quiz categories
- ⚡ 3 difficulty levels
- ⏱️ Time-based scoring (max 100, min 10 points)
- 🏆 Live leaderboard
- 📊 Player statistics (streaks, accuracy, avg time)
- 📜 Game history view
- 🔄 Real-time progress tracking during generation

**Main Components:**
- `QuizSetup.tsx` - Game configuration screen
- `QuizQuestion.tsx` - Question display with timer
- `QuizOption.tsx` - Answer option buttons
- `Leaderboard.tsx` - Real-time score display
- `QuizHistory.tsx` - Past games archive
- `QuizResults.tsx` - End-of-game summary

**State Management:**
```typescript
// quizStore.ts
interface QuizStore {
  currentGame: QuizGame | null;
  players: Player[];
  currentQuestion: Question | null;
  leaderboard: LeaderboardEntry[];
  gameHistory: CompletedGame[];
  createGame: (config: GameConfig) => Promise<void>;
  startGame: () => Promise<void>;
  submitAnswer: (playerId: string, answerId: string) => Promise<void>;
  nextRound: () => Promise<void>;
}
```

### 3. Navigation

**Components:**
- `Header.tsx` - App header with logo and nav links
- `Navigation.tsx` - Desktop navigation menu
- `MobileNav.tsx` - Mobile hamburger menu

**Routes:**
- `/` - Chat interface
- `/quiz` - Quiz game
- `/quiz/history` - Game history (optional)

## 🎨 Styling

### Tailwind CSS

We use Tailwind CSS for utility-first styling:

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        mainz: {
          red: '#C4122F',      // FSV Mainz 05 red
          white: '#FFFFFF',    // FSV Mainz 05 white
          dark: '#1a1a1a',     // Dark mode background
        },
      },
    },
  },
};
```

### Custom CSS

Global styles in `src/styles/index.css`:
- Tailwind base, components, utilities
- Custom animations
- Typography overrides
- Dark mode support

## 🔌 API Integration

### Axios Configuration (`services/api.ts`)

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor (add auth tokens, etc.)
api.interceptors.request.use(/* ... */);

// Response interceptor (handle errors)
api.interceptors.response.use(/* ... */);

export default api;
```

### Service Modules

**Chat Service (`services/chatService.ts`):**
```typescript
export const chatService = {
  createSession: () => api.post('/api/chat/session'),
  getSession: (id: string) => api.get(`/api/chat/session/${id}`),
  sendMessage: (sessionId: string, text: string) =>
    api.post('/api/chat/message', { sessionId, text }),
  deleteSession: (id: string) => api.delete(`/api/chat/session/${id}`),
};
```

**Quiz Service (`services/quizService.ts`):**
```typescript
export const quizService = {
  createGame: (config: GameConfig) => api.post('/api/quiz/game', config),
  startGame: (gameId: string) => api.post(`/api/quiz/game/${gameId}/start`),
  getQuestion: (gameId: string) => api.get(`/api/quiz/game/${gameId}/question`),
  submitAnswer: (gameId: string, data: AnswerData) =>
    api.post(`/api/quiz/game/${gameId}/answer`, data),
  getLeaderboard: (gameId: string) =>
    api.get(`/api/quiz/game/${gameId}/leaderboard`),
  getGameHistory: () => api.get('/api/quiz/games'),
};
```

## 🧩 Reusable Components

### UI Component Library

Located in `src/components/ui/`:

**Button.tsx:**
```typescript
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}
```

**Card.tsx:**
```typescript
interface CardProps {
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}
```

**Input.tsx:**
```typescript
interface InputProps {
  type?: 'text' | 'email' | 'password' | 'number';
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
}
```

**Alert.tsx:**
```typescript
interface AlertProps {
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
  onClose?: () => void;
}
```

## 🧪 Testing (Planned)

```bash
# Run tests (when implemented)
npm run test

# Watch mode
npm run test:watch

# Coverage report
npm run test:coverage
```

**Testing Strategy:**
- **Unit Tests**: Component logic, utility functions
- **Integration Tests**: API service calls, store interactions
- **E2E Tests**: User flows (create session, play quiz, etc.)

**Testing Tools (to be added):**
- Vitest (unit tests)
- Testing Library (component tests)
- Playwright (E2E tests)

## 🏗️ Build & Deployment

### Development Build

```bash
# Start dev server with hot reload
npm run dev
```

### Production Build

```bash
# Build for production
npm run build

# Output: dist/ directory

# Preview production build
npm run preview
```

### Build Configuration

**Vite Config (`vite.config.ts`):**
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
```

### Deployment Options

**Static Hosting (Vercel, Netlify, GitHub Pages):**
```bash
npm run build
# Deploy dist/ directory
```

**Docker:**
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Environment Variables (Production):**
```bash
VITE_API_URL=https://api.your-domain.com
```

## 🎨 Design System

### Colors

| Name | Hex | Usage |
|------|-----|-------|
| Primary Red | `#C4122F` | Buttons, links, accents |
| White | `#FFFFFF` | Backgrounds, text |
| Dark Gray | `#1a1a1a` | Dark mode background |
| Light Gray | `#f5f5f5` | Light mode background |

### Typography

- **Headings**: System font stack
- **Body**: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto
- **Monospace**: "SF Mono", Monaco, Consolas (for SQL queries)

### Spacing

Tailwind spacing scale (4px base):
- `p-2` = 8px
- `p-4` = 16px
- `p-6` = 24px
- `p-8` = 32px

## 🔧 Development Guidelines

### Component Structure

```typescript
// PreferredComponentStructure.tsx
import React from 'react';
import { ComponentProps } from './types';

export const ComponentName: React.FC<ComponentProps> = ({ prop1, prop2 }) => {
  // 1. Hooks
  const [state, setState] = useState(initialValue);

  // 2. Derived state
  const derivedValue = useMemo(() => computeValue(state), [state]);

  // 3. Event handlers
  const handleClick = () => {
    // Handle event
  };

  // 4. Effects
  useEffect(() => {
    // Side effect
  }, [dependencies]);

  // 5. Render
  return (
    <div className="...">
      {/* JSX */}
    </div>
  );
};
```

### State Management (Zustand)

```typescript
// stores/exampleStore.ts
import { create } from 'zustand';

interface ExampleStore {
  // State
  count: number;
  user: User | null;

  // Actions
  increment: () => void;
  setUser: (user: User) => void;
}

export const useExampleStore = create<ExampleStore>((set) => ({
  count: 0,
  user: null,
  increment: () => set((state) => ({ count: state.count + 1 })),
  setUser: (user) => set({ user }),
}));
```

### Error Handling

```typescript
try {
  const response = await api.post('/endpoint', data);
  // Handle success
} catch (error) {
  if (axios.isAxiosError(error)) {
    // Handle API error
    console.error('API Error:', error.response?.data);
  } else {
    // Handle other errors
    console.error('Error:', error);
  }
}
```

## 📦 Key Dependencies

| Package | Purpose |
|---------|---------|
| `react` | UI framework |
| `react-dom` | React DOM renderer |
| `react-router-dom` | Routing |
| `zustand` | State management |
| `axios` | HTTP client |
| `lucide-react` | Icons |
| `clsx` | Conditional classNames |
| `date-fns` | Date formatting |

## 🐛 Troubleshooting

### Common Issues

**1. API Connection Failed**
```
Error: Network Error
```
**Solution:** Check if backend is running on `http://localhost:8000`

**2. CORS Error**
```
Access-Control-Allow-Origin header is missing
```
**Solution:** Ensure backend has CORS configured for `http://localhost:3000`

**3. Build Errors**
```
Module not found
```
**Solution:** Run `npm install` to ensure all dependencies are installed

**4. Hot Reload Not Working**
```
Changes not reflected
```
**Solution:** Restart dev server with `npm run dev`

## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Test locally
4. Run linter: `npm run lint`
5. Build: `npm run build`
6. Submit PR

## 📚 Resources

- **React Docs**: https://react.dev
- **Vite Docs**: https://vitejs.dev
- **Tailwind Docs**: https://tailwindcss.com
- **Zustand Docs**: https://github.com/pmndrs/zustand
- **React Router**: https://reactrouter.com

## 📄 License

See main repository LICENSE.

---

**Built with ⚛️ React + ⚡ Vite for FSV Mainz 05**
