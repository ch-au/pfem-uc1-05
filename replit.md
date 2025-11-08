# FSV Mainz 05 Application - Replit Setup

## Overview
A TypeScript-based web application for FSV Mainz 05 football club featuring:
- **"Frag Mainz 05"**: AI-powered chat assistant with Natural Language to SQL
- **"05 Quizduell"**: AI-generated multiplayer quiz

## Technology Stack
- **Frontend**: React 19 + Vite + TypeScript (port 5000)
- **Backend**: Node.js + Fastify + TypeScript (port 8000)
- **AI**: OpenRouter API (anthropic/claude-3.5-sonnet) - 300+ models available
- **Observability**: Langfuse for AI tracing and prompt management
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
- `OPENROUTER_API_KEY`: OpenRouter API key for AI features (https://openrouter.ai)

Optional (but recommended):
- `LANGFUSE_PUBLIC_KEY`: For AI observability and prompt management
- `LANGFUSE_SECRET_KEY`: For AI observability and prompt management
- `OPENROUTER_MODEL`: Override default model (default: `anthropic/claude-3.5-sonnet`)

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

## AI Model Configuration

**OpenRouter Integration:**
- Default model: `anthropic/claude-3.5-sonnet`
- Alternative models available: 300+ models from OpenAI, Google, Anthropic, Meta, etc.
- To switch models: Set `OPENROUTER_MODEL` environment variable to any model from https://openrouter.ai/models

**Langfuse Prompt Management:**
- Prompts can be managed in Langfuse dashboard when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set
- Falls back to local prompts in `prompts/fallback/` when Langfuse is not configured
- Supports versioning and A/B testing of prompts

## Known Issues
1. **Package Manager**: Converted from pnpm to npm due to Replit environment compatibility issues.
2. **Database Schema**: Fallback prompts were updated to remove references to non-existent materialized views. Using base tables with JOINs instead.

## Recent Changes (2025-11-08)

### OpenRouter Migration
- **Migrated from Google Gemini to OpenRouter API** for greater model flexibility
- Installed `@openrouter/sdk` TypeScript SDK
- Created `OpenRouterService` to handle AI requests with structured outputs
- Updated all AI prompt executions to use OpenRouter (chat SQL generator, answer formatter, quiz generators)
- Configured default model: `anthropic/claude-3.5-sonnet`
- Maintained full Langfuse tracing integration for AI observability
- Updated fallback prompts to remove references to non-existent materialized views

### Earlier Changes
- Migrated from Python/FastAPI to Node.js/TypeScript stack
- Configured for Replit environment (port 5000 for frontend)
- Updated to use external Neon database via DATABASE_URL
- Fixed TypeScript LSP errors
- Added deployment configuration
- Extended chat_messages table with AI metadata columns
