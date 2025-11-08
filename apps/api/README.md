# FSV Mainz 05 API Backend

TypeScript/Node.js Backend mit Gemini AI Integration für Chat & Quiz Features.

## Features

- 🤖 **Chat Interface**: Natural Language to SQL mit Gemini AI
- 🎮 **Quiz System**: KI-generierte Fragen mit Multiplayer Support
- 📊 **Langfuse Integration**: Tracing & Observability für AI Calls
- 🔒 **Type-Safe**: Vollständig typisiert mit TypeScript + Zod
- 🧪 **Tested**: Unit, Integration & E2E Tests mit Vitest

## Quick Start

```bash
# Install dependencies (from project root)
pnpm install

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Run database migrations
psql $DB_URL -f ../../database/migrations/002_extend_schema_for_ts_app.sql

# Start development server
pnpm dev

# API runs on http://localhost:8000
```

## Project Structure

```
apps/api/
├── src/
│   ├── config/           # Configuration & Environment
│   ├── routes/           # API Route Handlers
│   ├── services/
│   │   ├── ai/          # Gemini, Langfuse, Prompts
│   │   ├── chat/        # Chat Business Logic
│   │   ├── quiz/        # Quiz Business Logic
│   │   └── database/    # PostgreSQL Service
│   ├── __tests__/       # Test Suite
│   └── server.ts        # Fastify Server Entry
├── package.json
├── vitest.config.ts
└── README.md
```

## Environment Variables

Required:
```bash
DB_URL=postgresql://user:pass@host:port/db?sslmode=require
GEMINI_API_KEY=AIza...  # From ai.google.dev/aistudio
```

Optional:
```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

NODE_ENV=development
API_PORT=8000
API_HOST=0.0.0.0
```

## API Endpoints

### Health
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed system status

### Chat
- `POST /api/chat/session` - Create new chat session
- `GET /api/chat/session/:id` - Get session history
- `POST /api/chat/message` - Send message & get AI response
- `DELETE /api/chat/session/:id` - Delete session

### Quiz
- `POST /api/quiz/game` - Create quiz game
- `POST /api/quiz/game/:id/start` - Start game
- `GET /api/quiz/game/:id` - Get game state
- `GET /api/quiz/game/:id/question` - Get current question
- `POST /api/quiz/game/:id/answer` - Submit answer
- `POST /api/quiz/game/:id/next` - Advance to next round
- `GET /api/quiz/game/:id/leaderboard` - Get leaderboard

See [API Documentation](./API.md) for detailed endpoint specs.

## Testing

```bash
# Run all tests
pnpm test

# Watch mode
pnpm test:watch

# Unit tests only (no DB required)
pnpm test:unit

# Integration tests (requires DB + API keys)
pnpm test:integration

# E2E tests
pnpm test:e2e

# Coverage report
pnpm test:coverage
```

See [Test Report](./TEST_REPORT.md) for details.

## Development

```bash
# Start with hot reload
pnpm dev

# Type checking
pnpm lint

# Build for production
pnpm build

# Run production build
pnpm start
```

## AI Prompts

### Langfuse (Cloud)
Prompts werden von Langfuse geladen wenn `LANGFUSE_*` keys gesetzt sind.

### Local Fallback
Bei fehlender Langfuse-Config: Automatischer Fallback zu `/prompts/fallback/*.txt`

Prompts:
1. `chat-sql-generator.txt` - Frage → SQL
2. `chat-answer-formatter.txt` - SQL Result → Antwort
3. `quiz-question-generator.txt` - Kategorie → Fragen
4. `quiz-answer-generator.txt` - SQL → Richtig + Falsch

## Architecture

### AI Flow (Chat)
```
User Frage
  ↓
[Langfuse Prompt: chat-sql-generator]
  ↓
Gemini API (JSON Mode)
  ↓
SQL Query generieren
  ↓
PostgreSQL ausführen (mit Safety Checks)
  ↓
[Langfuse Prompt: chat-answer-formatter]
  ↓
Gemini API (JSON Mode)
  ↓
Formatierte Antwort auf Deutsch
  ↓
Save to DB + Return to User
```

### AI Flow (Quiz)
```
Game erstellen (Kategorie + Schwierigkeit)
  ↓
[Langfuse Prompt: quiz-question-generator]
  ↓
Gemini API → N Fragen generieren
  ↓
Für jede Frage:
  ├─ SQL ausführen → Daten holen
  ├─ [Langfuse Prompt: quiz-answer-generator]
  ├─ Gemini API → Richtige Antwort + 3 Falsche
  └─ In DB speichern
  ↓
Game ready zum Spielen
```

## Database

### Connection
- PostgreSQL 16+ (via `pg` driver)
- Connection Pooling (2-10 connections)
- SSL required in production

### Safety
- ✅ Only SELECT queries allowed (no INSERT/UPDATE/DELETE from AI)
- ✅ 5 second query timeout
- ✅ 200 row limit per query
- ✅ Prepared statements (SQL injection prevention)

## Monitoring

### Langfuse Dashboard
When enabled, all AI calls are traced:
- Prompt versions used
- Token usage
- Latency
- Errors

Access: https://cloud.langfuse.com

### Logs
Development: Pretty-printed with `pino-pretty`
Production: Structured JSON logs

## Deployment

### Requirements
- Node.js 20+
- PostgreSQL 16+
- Gemini API Key

### Railway / Render

```bash
# Build
pnpm build

# Start
NODE_ENV=production pnpm start
```

Set environment variables in platform dashboard.

### Docker

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build
CMD ["pnpm", "start"]
```

## Contributing

1. Create feature branch
2. Make changes
3. Run tests: `pnpm test`
4. Run linter: `pnpm lint`
5. Create PR

## Support

- 📖 Docs: `README_NEW_IMPLEMENTATION.md`
- 🧪 Tests: `TEST_REPORT.md`
- 🔌 API: `API.md`

## License

See main repository LICENSE.
