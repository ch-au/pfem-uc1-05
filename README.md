# FSV Mainz 05 Archive

A comprehensive database of **FSV Mainz 05** football history from **1905-2025** with natural language querying, semantic search, and a React frontend.

**Status:** Production Ready | **Last Updated:** 2025-11-26

---

## Database Stats

| Metric | Count |
|--------|-------|
| Matches | 3,956 |
| Players | 9,916 |
| Coaches | 566 |
| Teams | 585 |
| Goals | 8,312 |
| Cards | 5,768 |
| Seasons | 121 (1905-2025) |

**Database:** PostgreSQL 17 (Neon Cloud)
**Features:** Cohere embeddings, HNSW vector search, materialized views

---

## Quick Start

### 1. Backend Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start server
uvicorn backend.app:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 3. Test Database Connection

```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM matches;"
```

---

## Project Structure

```
05app/
├── backend/
│   ├── app.py              # FastAPI application
│   ├── final_agent.py      # LLM SQL agent
│   ├── chatbot_service.py  # Chat service
│   └── config.py           # Configuration
├── frontend/               # React + TypeScript
├── database/
│   ├── 001_create_schema.sql
│   ├── 002_materialized_views.sql
│   ├── sync_sqlite_to_postgres.py
│   └── generate_embeddings.py
├── parsing/
│   └── comprehensive_fsv_parser.py
├── docs/                   # Documentation
│   ├── DATABASE_SCHEMA.md  # Schema reference
│   ├── DATA_QUALITY_REPORT.md
│   └── README.md           # Docs index
├── fsvarchiv/              # Source HTML files
├── fsv_archive_complete.db # SQLite (parser output)
└── archive/                # Old files
```

---

## Key Features

### Semantic Search
Find players/teams using natural language:
```sql
-- Find players similar to "Klopp"
SELECT name FROM players
ORDER BY name_embedding <=> (SELECT name_embedding FROM players WHERE name = 'JÜRGEN KLOPP')
LIMIT 5;
```

### Pre-computed Statistics
Fast queries via materialized views:
```sql
SELECT name, total_matches, wins, goals, assists
FROM mv_player_career_stats
WHERE normalized_name LIKE '%klopp%';
```

### Chat Interface
Natural language queries converted to SQL with context-aware responses.

---

## Environment Variables

```bash
# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://...

# LLM APIs
OPENAI_API_KEY=sk-...
COHERE_API_KEY=...

# Observability (optional)
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

---

## Database Scripts

| Script | Purpose |
|--------|---------|
| `database/001_create_schema.sql` | Create all tables |
| `database/002_materialized_views.sql` | Create views |
| `database/sync_sqlite_to_postgres.py` | Sync from SQLite |
| `database/generate_embeddings.py` | Generate Cohere embeddings |
| `parsing/comprehensive_fsv_parser.py` | Parse HTML → SQLite |

### Rebuild Database

```bash
# 1. Parse HTML to SQLite
python parsing/comprehensive_fsv_parser.py

# 2. Create PostgreSQL schema
psql $DATABASE_URL -f database/001_create_schema.sql

# 3. Sync data
python database/sync_sqlite_to_postgres.py

# 4. Generate embeddings
python database/generate_embeddings.py

# 5. Create materialized views
psql $DATABASE_URL -f database/002_materialized_views.sql
```

---

## Documentation

- [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) - Complete schema reference
- [docs/DATA_QUALITY_REPORT.md](docs/DATA_QUALITY_REPORT.md) - Data quality analysis
- [docs/CHATBOT_DESIGN.md](docs/CHATBOT_DESIGN.md) - Chat system architecture
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - Version history

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send chat message |
| `/chat/sessions` | POST | Create session |
| `/chat/sessions/{id}` | GET | Get session |
| `/health` | GET | Health check |

---

## Testing

```bash
# Test API
pytest tests/

# Test parser
python tests/test_parser.py

# Verify data
psql $DATABASE_URL -c "SELECT name, total_matches FROM mv_player_career_stats ORDER BY total_matches DESC LIMIT 10;"
```

---

## License

Parses publicly available historical data from the fsv05.de archive.
