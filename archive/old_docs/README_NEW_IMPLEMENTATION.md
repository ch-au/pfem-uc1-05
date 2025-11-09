# FSV Mainz 05 Interactive Platform - Neue TypeScript Implementation

## 🎯 Übersicht

Eine moderne TypeScript-basierte Webapp mit zwei Hauptfunktionen:

1. **"Frag Mainz 05"** - Intelligenter Chat-Assistent mit Natural Language to SQL
2. **"05 Quizduell"** - KI-generiertes Multiplayer-Quiz

### Technologie-Stack

- **Backend**: Node.js + TypeScript + Fastify
- **Frontend**: React 19 + TypeScript + Vite (noch zu migrieren)
- **AI**: Google Gemini API (gemini-2.0-flash-exp)
- **Tracing**: Langfuse (mit lokalen Fallback-Prompts)
- **Database**: PostgreSQL (erweitert bestehende Schema)
- **Monorepo**: pnpm + Turborepo

## 🏗️ Projekt-Struktur

```
pfem-uc1-05/
├── apps/
│   └── api/                      # TypeScript Backend (NEU)
│       ├── src/
│       │   ├── config/           # Env & Schema Context
│       │   ├── services/
│       │   │   ├── ai/           # Gemini, Langfuse, Prompts
│       │   │   ├── chat/         # Chat Business Logic
│       │   │   ├── quiz/         # Quiz Business Logic
│       │   │   └── database/     # PostgreSQL Service
│       │   ├── routes/           # API Routes
│       │   └── server.ts         # Fastify Server
│       └── package.json
│
├── packages/
│   └── shared-types/             # Shared TypeScript Types
│       └── src/
│           ├── database.types.ts
│           ├── chat.types.ts
│           └── quiz.types.ts
│
├── prompts/
│   └── fallback/                 # Lokale Prompt-Fallbacks (TXT)
│       ├── chat-sql-generator.txt
│       ├── chat-answer-formatter.txt
│       ├── quiz-question-generator.txt
│       └── quiz-answer-generator.txt
│
├── database/
│   └── migrations/
│       ├── 001_existing_schema.sql       # Baseline (quiz_schema.sql)
│       └── 002_extend_schema_for_ts_app.sql  # Erweiterungen (NEU)
│
├── backend/                      # Python Backend (LEGACY - bleibt intakt)
└── frontend/                     # React Frontend (noch zu migrieren)
```

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Node.js 20+ und pnpm installieren
node --version  # >= 20.0.0
pnpm --version  # >= 9.0.0

# Falls pnpm nicht installiert:
npm install -g pnpm@9
```

### 2. Environment Setup

```bash
# .env Datei erstellen
cp .env.example .env

# .env anpassen mit:
# - DB_URL (PostgreSQL Connection String)
# - GEMINI_API_KEY (Google AI Studio API Key)
# - LANGFUSE_* (optional - verwendet sonst lokale Prompts)
```

### 3. Dependencies installieren

```bash
# Im Root-Verzeichnis
pnpm install
```

### 4. Database Migration

```bash
# PostgreSQL muss bereits laufen mit bestehenden Daten

# Schema erweitern (fügt nur neue Tabellen/Spalten hinzu)
psql $DB_URL -f database/migrations/002_extend_schema_for_ts_app.sql

# Oder via npm script (wenn implementiert):
# pnpm db:migrate
```

### 5. Starten

```bash
# API Server starten
pnpm dev:api

# Server läuft auf http://localhost:8000
# Health Check: http://localhost:8000/health
```

## 📡 API Endpoints

### Chat Endpoints

```bash
# Neue Session erstellen
POST /api/chat/session
→ { "session_id": "...", "created_at": "...", "expires_at": "..." }

# Chat History abrufen
GET /api/chat/session/:sessionId
→ { "session_id": "...", "messages": [...] }

# Nachricht senden
POST /api/chat/message
Body: { "session_id": "...", "content": "Wer ist Rekordtorschütze?" }
→ { "message_id": "...", "role": "assistant", "content": "...", "metadata": {...} }

# Session löschen
DELETE /api/chat/session/:sessionId
```

### Quiz Endpoints

```bash
# Neues Spiel erstellen
POST /api/quiz/game
Body: {
  "difficulty": "medium",
  "num_rounds": 10,
  "game_mode": "classic",
  "player_names": ["Alice", "Bob"]
}
→ { "game_id": "...", "status": "pending", ... }

# Spiel starten
POST /api/quiz/game/:gameId/start
→ { "game_id": "...", "status": "in_progress", "current_round": 1 }

# Aktuelle Frage abrufen
GET /api/quiz/game/:gameId/question
→ { "question_id": "...", "question_text": "...", "alternatives": [...] }

# Antwort einreichen
POST /api/quiz/game/:gameId/answer
Body: { "player_name": "Alice", "answer": "Bopp", "time_taken": 12.5 }
→ { "is_correct": true, "correct_answer": "Bopp", "points_earned": 75 }

# Nächste Runde
POST /api/quiz/game/:gameId/next
→ { "current_round": 2, ... }

# Leaderboard
GET /api/quiz/game/:gameId/leaderboard
→ { "game_id": "...", "leaderboard": [...] }
```

### Health Endpoints

```bash
GET /health
GET /health/detailed
```

## 🤖 AI Flow-Architektur

### Chat-Flow (2 Prompts)

```
User-Frage
    ↓
[PROMPT 1: chat-sql-generator]
    ↓ (Gemini + Langfuse oder lokaler Fallback)
SQL Query generieren
    ↓
PostgreSQL ausführen
    ↓
[PROMPT 2: chat-answer-formatter]
    ↓ (Gemini + Langfuse oder lokaler Fallback)
Formatierte Antwort auf Deutsch
    ↓
Response an User
```

### Quiz-Flow (2 Prompts)

```
Game erstellen + Kategorie wählen
    ↓
[PROMPT 3: quiz-question-generator]
    ↓ (Gemini generiert N Fragen)
Für jede Frage:
    ├─ SQL Query ausführen → Daten holen
    ↓
[PROMPT 4: quiz-answer-generator]
    ├─ Korrekte Antwort extrahieren
    └─ 3 falsche Alternativen generieren
    ↓
Speichern in DB (quiz_questions + quiz_rounds)
    ↓
Game ready zum Spielen
```

## 📝 Prompt Management

### Langfuse (Cloud)

Wenn `LANGFUSE_PUBLIC_KEY` und `LANGFUSE_SECRET_KEY` in `.env` gesetzt sind:

- Prompts werden von Langfuse Cloud geladen
- Alle AI-Aufrufe werden getraced
- Vollständiges Observability Dashboard

### Lokale Fallbacks

Bei fehlender Langfuse-Konfiguration:

- Prompts werden aus `prompts/fallback/*.txt` geladen
- Kein Tracing, aber volle Funktionalität
- Gut für Development ohne Cloud-Abhängigkeit

## 🗄️ Datenbank-Schema-Erweiterungen

Die Migration `002_extend_schema_for_ts_app.sql` fügt hinzu:

**Neue Tabellen:**
- `quiz_categories` - Kategorisierung von Quiz-Fragen
- `quiz_players` - Spieler-Statistiken über alle Spiele

**Erweiterte Spalten:**
- `quiz_questions`: `category_id`, `langfuse_trace_id`, `answer_type`, `times_used`, etc.
- `quiz_games`: `game_mode`, `category_id`
- `quiz_answers`: `quiz_player_id`
- `chat_messages`: `langfuse_trace_id`, `sql_query`, `confidence_score`, etc.

**Trigger:**
- Automatische Aktualisierung von Spieler-Stats
- Automatische Aktualisierung von Fragen-Stats

**WICHTIG:** Bestehende Daten bleiben intakt!

## 🧪 Testing

```bash
# Unit Tests (Vitest)
pnpm test

# Health Check
curl http://localhost:8000/health/detailed
```

## 📊 Monitoring

### Development

```bash
# Logs werden mit pino-pretty formatiert
pnpm dev:api

# Ausgabe zeigt:
# - SQL Query Times
# - AI Generation Times
# - Langfuse Trace IDs
# - Errors mit Stack Traces
```

### Production (mit Langfuse)

1. Gehe zu https://cloud.langfuse.com
2. Navigiere zu deinem Projekt
3. Siehe alle Traces für:
   - Chat SQL Generation
   - Chat Answer Formatting
   - Quiz Question Generation
   - Quiz Answer Generation

## 🔐 Sicherheit

- **SQL Injection**: Nur SELECT-Statements erlaubt, 5s Timeout
- **Rate Limiting**: TODO (via @fastify/rate-limit)
- **CORS**: In Production konfigurieren
- **Environment Variables**: Validiert mit Zod

## 📦 Deployment

### Option 1: Railway / Render

```bash
# Build
pnpm build

# Start
pnpm start
```

Environment Variables setzen:
- `DB_URL`
- `GEMINI_API_KEY`
- `LANGFUSE_*` (optional)
- `NODE_ENV=production`

### Option 2: Docker (TODO)

```dockerfile
FROM node:20-alpine
# ... siehe Dockerfile
```

## 🤝 Bestehende Python-Backend

Das Python-Backend in `/backend` bleibt **vollständig intakt** und funktional!

- Kann parallel laufen (auf anderem Port)
- Nutzt dieselbe Datenbank
- Migrations sind rückwärtskompatibel

## 📚 Nächste Schritte

- [ ] Frontend nach `apps/web` migrieren
- [ ] shadcn/ui + TailwindCSS integrieren
- [ ] WebSocket Support für Live-Quiz
- [ ] Rate Limiting
- [ ] Docker Setup
- [ ] E2E Tests
- [ ] Frontend UI Components für Chat & Quiz

## 🐛 Troubleshooting

### Langfuse Connection Failed

→ Check `LANGFUSE_*` keys oder nutze lokale Prompts (Keys weglassen)

### Database Connection Failed

→ Check `DB_URL` Format: `postgresql://user:pass@host:port/db?sslmode=require`

### Gemini API Error

→ Check `GEMINI_API_KEY` ist valid (von ai.google.dev/aistudio)

### Migration schlägt fehl

→ Check ob `quiz_schema.sql` (001) bereits angewendet wurde

## 📄 Lizenz

Siehe Hauptprojekt README.
