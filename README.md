# FSV Mainz 05 Interactive Database App 🔴⚪

**Status:** ✅ Production Ready | **Last Updated:** 2025-11-09

An interactive web application featuring **120 years of FSV Mainz 05 football history** (1905-2025) with AI-powered chat and multiplayer quiz features. Built with React, TypeScript, Fastify, and PostgreSQL.

[![TypeScript](https://img.shields.io/badge/TypeScript-5.3-blue.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-19.1-61dafb.svg)](https://reactjs.org/)
[![Node.js](https://img.shields.io/badge/Node.js-20+-339933.svg)](https://nodejs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791.svg)](https://www.postgresql.org/)

---

## 🎯 What is this?

This is a **full-stack TypeScript application** that brings 120 years of FSV Mainz 05 football history to life through:

1. **🤖 AI Chat Interface**: Ask questions in natural language (German), get intelligent answers powered by Google Gemini AI that queries the historical database
2. **🎮 Interactive Quiz Game**: Multiplayer trivia with AI-generated questions based on real historical data
3. **📊 Comprehensive Database**: 3,305 matches, 10,094 players, 5,652 goals spanning 1905-2025

---

## 🗂️ Project Structure (Monorepo)

This is a **Turborepo monorepo** with the following structure:

```
/
├── apps/
│   └── api/                  # 🔷 TypeScript/Node.js Backend (Fastify + Gemini AI)
├── packages/
│   └── shared-types/         # 📦 Shared TypeScript types
├── frontend/                 # ⚛️  React + TypeScript Frontend (Vite)
├── database/
│   ├── migrations/           # 🗄️  PostgreSQL schema migrations
│   └── seed/                 # 🌱 Database seed scripts
├── prompts/                  # 🤖 AI prompts for Gemini
├── parsing/                  # 🔧 Historical data parser scripts
├── docs/                     # 📚 Detailed documentation
└── archive/                  # 📁 Legacy Python backend (archived)
```

**Package Manager:** npm workspaces with Turborepo
**Orchestration:** `turbo run dev/build/test`

---

## ✨ Features

### Chat Interface (`/`)
- 💬 **Natural Language Queries**: Ask questions in German about FSV Mainz 05 history
- 🧠 **AI-Powered**: Google Gemini converts questions to SQL queries
- 💾 **Session History**: Save and review past conversations
- 🎯 **Smart Suggestions**: Pre-defined question chips for quick access
- 📊 **Data Visualization**: See SQL queries and confidence scores

### Quiz Game (`/quiz`)
- 🎮 **Multiplayer Support**: 1-10 players compete simultaneously
- 🤖 **AI-Generated Questions**: Unique questions powered by real database data
- 📊 **6 Categories**: Top Scorers, Historic Matches, Players, Seasons, Opponents, Statistics
- 🏆 **Live Leaderboard**: Real-time scoring with time-based points
- 📈 **Game History**: Review past games and track performance
- ⚡ **Three Difficulty Levels**: Easy, Medium, Hard
- 🎯 **Multiple Modes**: Classic, Speed, Survival

### Database
- 📅 **120 Years of History**: 1905-2025
- ⚽ **3,305 Matches**: All competitions (Bundesliga, DFB-Pokal, European cups)
- 👥 **10,094 Players**: Complete player database
- 🥅 **5,652 Goals**: Every goal with minute and scorer
- 🟨🟥 **5,768 Cards**: Yellow and red cards
- 📋 **85,342 Appearances**: Player lineup data
- 🔄 **10,196 Substitutions**: In-game changes
- 🚀 **Materialized Views**: 100-400x faster queries

---

## 🚀 Quick Start

### Prerequisites
- **Node.js** 20+ (required)
- **PostgreSQL** 16+ with FSV Mainz 05 database
- **Google Gemini API Key** ([Get one here](https://ai.google.dev/aistudio))

### 1. Clone & Install

```bash
# Clone the repository
git clone <repo-url>
cd pfem-uc1-05

# Install all dependencies (root + workspaces)
npm install
```

### 2. Configure Environment

Create `.env` file in the root:

```bash
# Database (Required)
DB_URL=postgresql://user:password@host:port/fsv05?sslmode=require

# Google Gemini AI (Required)
GEMINI_API_KEY=your_gemini_api_key

# Langfuse Observability (Optional)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Application
NODE_ENV=development
API_PORT=8000
WEB_PORT=3000
```

### 3. Run Database Migrations

```bash
npm run db:migrate
```

### 4. Start Development

```bash
# Start both frontend and backend
npm run dev

# Or start individually:
npm run dev:api    # API only (http://localhost:8000)
npm run dev:web    # Frontend only (http://localhost:3000)
```

🎉 **Done!** Open http://localhost:3000 in your browser.

---

## 📖 Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start both frontend & backend in dev mode |
| `npm run dev:api` | Start backend only (port 8000) |
| `npm run dev:web` | Start frontend only (port 3000) |
| `npm run build` | Build all apps for production |
| `npm run test` | Run all tests (unit + integration) |
| `npm run lint` | Run linters across all workspaces |
| `npm run db:migrate` | Run database migrations |
| `npm run db:seed` | Seed database with initial data |
| `npm run clean` | Clean all node_modules and build artifacts |

---

## 🏗️ Architecture Overview

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 19.1 + TypeScript + Vite | Modern UI with hot reload |
| **State Management** | Zustand | Lightweight state management |
| **Routing** | React Router v7 | Client-side routing |
| **Backend** | Fastify + TypeScript | High-performance API server |
| **Database** | PostgreSQL 16+ | Historical data storage |
| **AI** | Google Gemini 1.5 | Natural language processing |
| **Observability** | Langfuse (optional) | AI call tracing |
| **Type Safety** | TypeScript + Zod | End-to-end type safety |
| **Testing** | Vitest | Unit, integration, E2E tests |
| **Monorepo** | Turborepo + npm workspaces | Efficient build orchestration |

### AI Flow (Chat)

```
User Question (German)
  ↓
[Prompt: chat-sql-generator]
  ↓
Gemini API → Generate SQL
  ↓
PostgreSQL (with safety checks)
  ↓
[Prompt: chat-answer-formatter]
  ↓
Gemini API → Format answer
  ↓
Return to user + Save to DB
```

### AI Flow (Quiz)

```
Create Game (category + difficulty)
  ↓
[Prompt: quiz-question-generator]
  ↓
Gemini API → Generate questions with SQL
  ↓
For each question:
  ├─ Execute SQL query
  ├─ [Prompt: quiz-answer-generator]
  ├─ Gemini API → Generate 1 correct + 3 wrong answers
  └─ Save to database
  ↓
Game ready to play
```

---

## 📊 Database Schema

### Core Tables (26 total)

| Table | Records | Description |
|-------|---------|-------------|
| `teams` | 293 | FSV Mainz 05 + all opponents |
| `players` | 10,094 | Player master data |
| `matches` | 3,305 | Match results with scores |
| `goals` | 5,652 | Goal events (minute, player) |
| `cards` | 5,768 | Yellow/red cards |
| `match_lineups` | 85,342 | Starting XI & substitutes |
| `competitions` | 23 | Bundesliga, DFB-Pokal, European cups |
| `seasons` | 121 | 1905-2026 seasons |
| `chat_sessions` | - | Chat conversation history |
| `quiz_games` | - | Quiz game instances |
| `quiz_questions` | - | AI-generated question bank |

### Materialized Views (4 total)

1. **`mainz_match_results`** - All Mainz matches with full details (100-400x faster)
2. **`player_career_stats`** - Aggregated player statistics
3. **`season_performance`** - Season-by-season performance
4. **`competition_statistics`** - All-time stats by competition

**📚 Full Schema Documentation:** [docs/SCHEMA_DOCUMENTATION_2025.md](docs/SCHEMA_DOCUMENTATION_2025.md)

---

## 🧪 Testing

```bash
# Run all tests
npm run test

# Backend tests only
cd apps/api
npm run test

# Unit tests (no DB required)
npm run test:unit

# Integration tests (requires DB)
npm run test:integration

# E2E tests (full stack)
npm run test:e2e

# Watch mode
npm run test:watch
```

**Test Coverage:** See [apps/api/TEST_REPORT.md](apps/api/TEST_REPORT.md)

---

## 📚 Documentation

### 🎯 Getting Started
- **[README.md](README.md)** ← You are here (main overview)
- **[QUICK_START.md](QUICK_START.md)** - SQL query examples & database tips
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Developer contribution guide

### 🔧 Application
- **[apps/api/README.md](apps/api/README.md)** - Backend API documentation
- **[frontend/README.md](frontend/README.md)** - Frontend application guide
- **[packages/shared-types/](packages/shared-types/)** - Shared TypeScript types

### 🗄️ Database
- **[docs/SCHEMA_DOCUMENTATION_2025.md](docs/SCHEMA_DOCUMENTATION_2025.md)** - Complete schema reference
- **[docs/MATERIALIZED_VIEWS_REFERENCE.md](docs/MATERIALIZED_VIEWS_REFERENCE.md)** - Optimized query guide
- **[database/migrations/README.md](database/migrations/README.md)** - Migration history

### 🔧 Data Processing
- **[parsing/README.md](parsing/README.md)** - Historical data parser guide
- **[docs/PARSER_IMPROVEMENTS.md](docs/PARSER_IMPROVEMENTS.md)** - Parser documentation
- **[parsing/data_cleansing/README.md](parsing/data_cleansing/README.md)** - Data quality scripts

### 📈 Performance & Monitoring
- **[docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md)** - Database optimization
- **[apps/api/README.md#monitoring](apps/api/README.md#monitoring)** - Langfuse observability

### 📖 Project History
- **[COMPLETE_SUMMARY.md](COMPLETE_SUMMARY.md)** - Database optimization summary (Nov 2025)
- **[docs/CHANGELOG.md](docs/CHANGELOG.md)** - Version history

---

## 🔧 Advanced Usage

### Running the Data Parser

The parser extracts historical match data from fsv05.de HTML archives:

```bash
cd parsing
python comprehensive_fsv_parser.py
```

**Features:**
- Automatic league extraction
- Duplicate prevention
- European competition support
- Data validation & Unicode support

**Documentation:** [parsing/README.md](parsing/README.md)

### Refreshing Materialized Views

After importing new data:

```bash
psql $DB_URL << EOF
REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;
REFRESH MATERIALIZED VIEW CONCURRENTLY player_career_stats;
REFRESH MATERIALIZED VIEW CONCURRENTLY season_performance;
REFRESH MATERIALIZED VIEW CONCURRENTLY competition_statistics;
EOF
```

### Langfuse AI Monitoring

Enable optional AI observability:

1. Create account at https://cloud.langfuse.com
2. Get API keys
3. Add to `.env`:
   ```bash
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```

Tracks: prompt versions, token usage, latency, errors

---

## 🚀 Deployment

### Requirements
- Node.js 20+
- PostgreSQL 16+ with migrated schema
- Google Gemini API key
- (Optional) Langfuse account

### Production Build

```bash
# Install dependencies
npm install --production

# Build all apps
npm run build

# Run migrations
npm run db:migrate

# Start production server
NODE_ENV=production npm start
```

### Docker

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY . .
RUN npm run build
CMD ["npm", "start"]
```

### Environment Variables (Production)

```bash
NODE_ENV=production
DB_URL=postgresql://...
GEMINI_API_KEY=...
API_PORT=8000
API_HOST=0.0.0.0
```

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Quick Start:**
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `npm run test`
5. Run linter: `npm run lint`
6. Submit a pull request

---

## 📄 License

This project parses publicly available historical data from the fsv05.de archive.

---

## 📞 Support & Resources

- 🐛 **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- 📖 **Wiki**: [Project Wiki](https://github.com/your-repo/wiki)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)

---

## 🎯 Recent Updates (November 2025)

- ✅ **Fixed duplicate team issue** - Bundesliga data now visible (652 matches)
- ✅ **Added materialized views** - 100-400x query speedup
- ✅ **Unique constraints** - Prevent duplicate events
- ✅ **Foreign keys** - Enable proper table joins
- ✅ **Quiz feature** - Multiplayer trivia with AI-generated questions
- ✅ **TypeScript migration** - Modern type-safe backend
- ✅ **Langfuse integration** - AI observability

---

**⚽ Made with ❤️ for FSV Mainz 05 fans**
