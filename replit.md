# Overview

This is a comprehensive FSV Mainz 05 football statistics application featuring:

- **Natural Language SQL Query System**: Users can ask questions in plain language about FSV Mainz 05's history, and an AI agent converts them to SQL queries and returns results
- **AI-Powered Quiz Game**: Multiplayer quiz with AI-generated questions based on the historical database
- **Chat Assistant**: Conversational interface for exploring 120+ years of club history (1905-2025)
- **Comprehensive Database**: 3,305 matches, 10,094 players, 5,652 goals spanning from 1905 to present

The application combines a React TypeScript frontend with a dual-backend architecture:
- **Python/FastAPI**: Legacy backend for SQL agent and data parsing
- **Node.js/Fastify**: Modern backend for chat and quiz features

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture

**Framework**: React 19 + Vite + TypeScript  
**State Management**: Zustand for lightweight global state  
**Routing**: React Router v7  
**Styling**: CSS modules with utility classes (clsx)  
**Build Tool**: Vite for fast HMR and optimized production builds

**Key Design Decisions**:
- Component-based architecture with functional components and hooks
- Separated concerns between UI components, API client, and state management
- Proxy configuration to route API calls to backend (port 8000) from frontend dev server (port 5000)

## Backend Architecture

### Dual Backend Strategy

**Why Two Backends?**
- **Python/FastAPI** (legacy): Handles complex SQL agent logic, database parsing, and data processing
- **Node.js/Fastify** (modern): Provides high-performance API for chat and quiz features with better TypeScript integration

### Python Backend (FastAPI)

**Core Services**:
1. **FinalSQLAgent** (`backend/final_agent.py`): Converts natural language to SQL using LLM with semantic search
2. **ChatbotService** (`backend/chatbot_service.py`): Session-based conversational interface
3. **QuizService** (`backend/quiz_service.py`): Game state management, scoring, multiplayer support
4. **QuizGenerator** (`backend/quiz_generator.py`): AI-powered question generation from database facts
5. **LLMService** (`backend/llm_service.py`): LiteLLM wrapper with Langfuse observability

**Architecture Patterns**:
- **Service Layer Pattern**: Business logic separated into focused services
- **Repository Pattern**: Database access abstracted through dedicated modules
- **Structured LLM Outputs**: Pydantic models enforce type safety for AI responses
- **Connection Pooling**: psycopg2 connection pool for efficient database access

### Node.js Backend (Fastify)

**Location**: `apps/api/`  
**Purpose**: Modern TypeScript-first API for production deployments  
**Features**:
- Environment configuration via `@fastify/env`
- CORS handling via `@fastify/cors`
- Structured logging with Pino
- Schema validation with Zod

## Data Layer

### Database: PostgreSQL (Neon Cloud)

**Schema Overview** (26 tables + 4 materialized views):

**Core Entities**:
- `teams` (293 rows): Mainz + all opponents
- `players` (10,094 rows): Player master data
- `coaches`, `referees`: Staff and officials
- `competitions`, `seasons`, `season_competitions`: Competition organization

**Match Data**:
- `matches` (3,305 rows): Match metadata
- `match_lineups` (84,172 rows): Player appearances
- `goals` (5,652 rows): Goal events with minute/stoppage time
- `cards` (5,768 rows): Yellow/red card events
- `match_substitutions` (10,196 rows): Substitution events

**Performance Optimizations**:
- **Materialized Views**: Pre-aggregated statistics refreshed periodically
  - `mainz_match_results`: 160x faster match history queries
  - `player_career_stats`: 400x faster player statistics
  - `season_performance`: 300x faster season analysis
  - `competition_statistics`: 400x faster competition comparisons
- **107 Indexes**: Covering common query patterns (GIN trigram for text search, HNSW for vector similarity)
- **Unique Constraints**: Prevent duplicate events (cards, goals, lineups, substitutions)

**Connection Strategy**:
- **Unified Connection String**: Single `DB_URL` environment variable (Neon connection string with SSL)
- **Connection Pool**: Singleton pattern with 20 max connections, 30s idle timeout
- **Two Access Patterns**:
  - LangChain SQLDatabase for LLM-generated queries (SQLAlchemy URI)
  - Raw psycopg2 for administrative operations (DSN)

### SQLite (Parser Output)

The `comprehensive_fsv_parser.py` generates SQLite databases from HTML source files. These are then migrated to PostgreSQL for production use.

**Design Decision**: SQLite for parsing allows:
- Easy testing and validation before production deployment
- Standalone parsing without cloud database dependencies
- Efficient batch operations during initial data load

## AI/LLM Integration

### LiteLLM with Multi-Provider Support

**Model Selection**:
- **Default**: Gemini Flash (free, no API key required)
- **Configurable**: OpenAI, Anthropic, or any LiteLLM-supported model via environment variables

**Key Features**:
1. **Structured Outputs**: Pydantic models enforce response schemas
   - `SQLQueryResponse`: SQL query + explanation
   - `QuizQuestion`: Question + alternatives + metadata
   - `ChatResponse`: Answer + sources + confidence
2. **Observability**: Langfuse integration for tracing, prompt management, and evaluation
3. **Fallback Strategy**: Graceful degradation when API keys not provided

### Semantic Search (Optional)

**OpenAI Embeddings** (text-embedding-3-large, 3072 dimensions):
- Player/team name fuzzy matching for misspellings
- Semantic hints for SQL generation
- **Design Decision**: Embeddings are optional - system works without them using pattern matching

## Data Processing Pipeline

### Comprehensive Parser (`parsing/comprehensive_fsv_parser.py`)

**Purpose**: Extract structured data from HTML source files (1905-2025)

**Key Features**:
1. **Batch Operations**: In-memory deduplication before database insert
2. **Transaction Management**: One transaction per match with automatic rollback
3. **Data Validation**: Pre-insert validation of minutes, player IDs, team IDs
4. **Error Recovery**: Graceful handling with detailed statistics
5. **Team Consolidation**: Automatic normalization of historical team name variants

**Processing Flow**:
```
HTML Files → BeautifulSoup → Parse Entities → Validate → Batch Insert → Commit
```

**Validation Layers**:
- Pattern matching (e.g., filter out referee names, trainer names)
- Unicode validation (reject non-letter characters)
- Range validation (minutes 0-120, stoppage 0-20)
- Foreign key validation (player/team/match existence)

## Configuration Management

**Environment-First Configuration**:
- `.env` file for local development
- Environment variables for production (Replit Secrets)
- `backend/config.py`: Centralized configuration with sensible defaults

**Critical Variables**:
- `DB_URL`: PostgreSQL connection string
- `OPENROUTER_API_KEY`: Required for AI features
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`: Optional observability
- `LITELLM_DEFAULT_MODEL`: Model selection (defaults to Gemini Flash)

## Error Handling & Observability

**Logging Strategy**:
- Python: Standard `logging` module with file + console handlers
- Node.js: Pino structured logging

**Observability Stack**:
- **Langfuse**: LLM call tracing, prompt versioning, evaluation metrics
- **Database Logging**: Query execution times, connection pool stats
- **Error Statistics**: Parsing errors, validation failures tracked and reported

# External Dependencies

## Required Services

1. **Neon PostgreSQL Database**
   - Cloud-hosted PostgreSQL with pgvector extension
   - Connection via `DB_URL` environment variable
   - SSL/TLS required (`sslmode=require`)

2. **OpenRouter API** (https://openrouter.ai)
   - Unified API for 300+ LLM models
   - Used for: SQL generation, quiz generation, chat responses
   - Requires `OPENROUTER_API_KEY`
   - **Default model**: `google/gemini-2.5-flash-preview-09-2025` (optimized for quiz generation)
   - Alternative: `anthropic/claude-3.5-sonnet` (for chat)
   - **Note**: Gemini models return Markdown code blocks (```json ... ```), automatically stripped by OpenRouterService

## Optional Services

3. **Langfuse** (https://cloud.langfuse.com)
   - LLM observability and prompt management
   - Traces all AI interactions with metadata
   - Requires `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
   - Gracefully disabled if keys not provided

4. **OpenAI API** (for embeddings)
   - Used for semantic player/team name matching
   - Model: `text-embedding-3-large` (3072 dimensions)
   - Requires `OPENAI_API_KEY`
   - System works without embeddings (falls back to pattern matching)

## NPM Packages

**Production**:
- `fastify`: High-performance web framework
- `@google/generative-ai`: Gemini integration
- `pg`: PostgreSQL client
- `langfuse`: Observability SDK
- `zod`: Schema validation
- `dotenv`: Environment configuration

**Frontend**:
- `react`, `react-dom`: UI framework
- `react-router-dom`: Client-side routing
- `axios`: HTTP client
- `zustand`: State management
- `lucide-react`: Icon library

## Python Packages

**Core**:
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `psycopg2-binary`: PostgreSQL adapter
- `litellm`: Multi-provider LLM client
- `langfuse`: Observability
- `langchain-community`, `langchain-openai`: SQL agent utilities
- `pydantic`: Data validation
- `beautifulsoup4`: HTML parsing

**Data Processing**:
- `pandas`: Data manipulation (optional)
- `python-dotenv`: Environment variables

## Database Extensions

- **pgvector**: Vector similarity search for embeddings
- Built-in PostgreSQL features: JSONB, GIN indexes, materialized views, trigram similarity