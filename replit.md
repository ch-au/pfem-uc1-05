# FSV Mainz 05 Application - Replit Setup

## Overview
A TypeScript-based web application for FSV Mainz 05 football club featuring:
- **"Frag Mainz 05"**: AI-powered chat assistant with Natural Language to SQL
- **"05 Quizduell"**: AI-generated multiplayer quiz

## Technology Stack
- **Frontend**: React 19 + Vite + TypeScript (port 5000)
- **Backend**: Node.js + Fastify + TypeScript (port 8000)
- **AI**: Google Gemini API (gemini-2.0-flash-exp)
- **Database**: PostgreSQL (External Neon Database)
- **Package Manager**: npm (converted from pnpm for Replit compatibility)

## Project Structure
```
/
├── apps/
│   └── api/          # Backend API (Fastify + TypeScript)
├── frontend/         # React frontend (Vite)
├── packages/
│   └── shared-types/ # Shared TypeScript types
├── database/         # Database schemas and migrations
└── docs/            # Documentation
```

## Environment Variables
Required secrets in Replit:
- `DATABASE_URL`: External Neon PostgreSQL database connection string
- `GEMINI_API_KEY`: Google Gemini API key for AI features

Optional:
- `LANGFUSE_PUBLIC_KEY`: For AI observability
- `LANGFUSE_SECRET_KEY`: For AI observability

## Development

### Running Locally
Both workflows are configured to run automatically:
- **Frontend**: `http://localhost:5000` (webview)
- **Backend API**: `http://localhost:8000` (console)

### Database
The application connects to an external Neon PostgreSQL database containing:
- FSV Mainz 05 historical match data (1905-2025)
- Chat sessions and messages
- Quiz games and questions
- Player statistics and records

Database tables are pre-populated in the external database.

## Deployment
Configured for Replit Autoscale deployment:
- Builds both frontend and backend
- Serves frontend on port 5000
- Runs backend API on port 8000
- Frontend proxies API requests to backend

## Known Issues
1. **AI Prompt Length**: The database schema context is too long for `gemini-2.0-flash-exp` model, causing some AI requests to fail with 400 errors. The app handles this gracefully with fallback error messages. Consider using a model with larger context or shortening the system prompt.
2. **Package Manager**: Converted from pnpm to npm due to Replit environment compatibility issues.

## Recent Changes (2025-11-08)
- Migrated from Python/FastAPI to Node.js/TypeScript stack
- Configured for Replit environment (port 5000 for frontend)
- Updated to use external Neon database via DATABASE_URL
- Fixed TypeScript LSP errors
- Added deployment configuration
- Extended chat_messages table with AI metadata columns
