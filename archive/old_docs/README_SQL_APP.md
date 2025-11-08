# FSV Mainz 05 Natural Language SQL Assistant

A web application that allows you to query the FSV Mainz 05 historical database using natural language. It converts questions to SQL, executes against SQLite, and summarizes results. Optional pgvector in Postgres accelerates semantic name resolution for players and opponents.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2) Environment

Create a `.env` file. **For Neon database (recommended):**
```bash
# Required
OPENAI_API_KEY=sk-...
DB_URL=postgresql://username:password@ep-cool-cloud-123456.us-east-1.aws.neon.tech/neondb?sslmode=require

# Optional (defaults shown)
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_EMBEDDING_DIM=3072
PG_SCHEMA=public
```

**Alternative - Discrete Postgres settings:**
```bash
OPENAI_API_KEY=sk-...
PG_ENABLED=true
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DATABASE=fsv05
PG_USER=postgres
PG_PASSWORD=postgres
PG_SCHEMA=public
PG_SSLMODE=require
```

### 3) Test Your Connection

Verify your Neon database connection works:
```bash
python test_connections.py
```

### 4) Ingest Data

Parse HTML files and populate your Neon database:
```bash
# Full reset and ingestion (recommended for first run)
python ingest_postgres.py --reset

# Or incremental update
python ingest_postgres.py
```

### 5) Precompute Embeddings (optional but recommended)

Populate Postgres `name_embeddings` with player/opponent name vectors for semantic lookup:
```bash
python precompute_embeddings.py
```

### 6) Run the Application

```bash
python run.py --host 127.0.0.1 --port 8000 --log-file ./logs/server.log
# or
./start_server.sh
```

Visit `http://127.0.0.1:8000`.

## 🔧 Configuration

### Neon Database Setup (Recommended)

1. **Create a Neon project** at [console.neon.tech](https://console.neon.tech)
2. **Copy your connection string** (format: `postgresql://user:pass@host/db?sslmode=require`)
3. **Add to `.env`** as `DB_URL=your_neon_connection_string`
4. **Test connection**: `python test_connections.py`

### Other Configuration

Edit `config.py` or use environment variables:
- **DB_URL**: Neon connection string (auto-enables Postgres)
- **OPENAI_API_KEY**: Required for LLM and embeddings
- **Models**: `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_EMBEDDING_DIM`
- **Legacy**: Discrete `PG_*` settings if not using DB_URL

## 📝 Example Queries

Try these natural language questions:

- "Who are the top 10 scorers of all time?"
- "Show me all matches against Bayern Munich"
- "What was FSV's biggest victory?"
- "List all players with more than 50 goals"
- "How many home games did FSV win in the 2022-23 season?"
- "Who scored the most penalties?"

## 🏗️ Architecture

- **Frontend**: HTML/JavaScript with Tailwind CSS
- **Backend**: FastAPI with async endpoints  
- **AI**: LangChain + OpenAI (Chat + Embeddings)
- **Database**: Postgres (Neon) with pgvector for semantic lookup
- **Data Source**: HTML files parsed from FSV Mainz 05 archive

## 🔍 API Endpoints

- `GET /`: Web interface
- `POST /query`: Process natural language queries
- `GET /health`: Health check and connection status
- `GET /schema`: Database schema information

## 🗄️ Database Schema

**Core Tables** (used for queries):

- `Players(player_id INTEGER PRIMARY KEY, player_name TEXT, player_link TEXT)`
- `Opponents(opponent_id INTEGER PRIMARY KEY, opponent_name TEXT, opponent_link TEXT)`
- `Seasons(season_id INTEGER PRIMARY KEY, season_name TEXT, league_name TEXT, total_matches INTEGER)`
- `Matches(match_id INTEGER PRIMARY KEY, season_id INTEGER, opponent_id INTEGER, gameday INTEGER, is_home_game BOOLEAN, mainz_goals INTEGER, opponent_goals INTEGER, result_string TEXT, match_details_url TEXT)`
- `Match_Lineups(lineup_id INTEGER PRIMARY KEY, match_id INTEGER, player_id INTEGER, is_starter BOOLEAN, is_captain BOOLEAN, jersey_number INTEGER, substituted_minute INTEGER, yellow_card BOOLEAN, red_card BOOLEAN)`
- `Substitutions(substitution_id INTEGER PRIMARY KEY, match_id INTEGER, minute INTEGER, player_in_id INTEGER, player_out_id INTEGER)`
- `Goals(goal_id INTEGER PRIMARY KEY, match_id INTEGER, player_id INTEGER, goal_minute INTEGER, is_penalty BOOLEAN, is_own_goal BOOLEAN, assisted_by_player_id INTEGER, score_at_time TEXT)`

**Additional Tables:**
- `Player_Careers`: Career history across clubs
- `Player_Season_Stats`: Season-by-season statistics  
- `Coaches`: Manager information
- `Referees`: Match officials

**Notes:**
- Postgres booleans: Use `= TRUE`/`= FALSE` (e.g., `m.is_home_game = TRUE` for home)
- Minutes played pattern:
  - Starters: `COALESCE(ml.substituted_minute, 90)`
  - Substitutes: `90 - (SELECT MIN(sub.minute) WHERE sub.player_in_id = ml.player_id AND sub.match_id = ml.match_id)`

## 🧭 Postgres pgvector Schema (semantic lookup)

The precompute script creates and maintains a compact vector index for names.

Extension
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
Table
```sql
CREATE TABLE IF NOT EXISTS public.name_embeddings (
  kind TEXT NOT NULL,                -- 'player' | 'opponent'
  entity_id INTEGER NOT NULL,        -- player_id or opponent_id from SQLite
  name TEXT NOT NULL,
  embedding vector(3072),            -- adjust to OPENAI_EMBEDDING_DIM
  PRIMARY KEY(kind, entity_id)
);
```
Populate
- `python precompute_embeddings.py` embeds all names and upserts into `name_embeddings`.

Query-time retrieval
```sql
-- nearest players to a query vector (negative inner product)
SELECT entity_id, name
FROM public.name_embeddings
WHERE kind = 'player'
ORDER BY embedding <#> $1::vector
LIMIT 3;
```
Refer to pgvector operators `<->` (L2), `<#>` (negative inner product), `<=>` (cosine) in the pgvector docs: [pgvector repository](https://github.com/pgvector/pgvector).

## 🔁 NL → SQL Pipeline
1) **Live schema introspection** (`SQLDatabase.get_table_info()`)
2) **Semantic hints** from pgvector: embed the question, fetch top player/opponent candidates
3) **Entity resolution**: apply `player_id`/`opponent_id` filters when string-confirmed match exists
4) **SQL generation** (JSON-only) with guardrails:
   - SELECT-only, single statement
   - Postgres TRUE/FALSE booleans
   - Use `Seasons` for season labels  
   - Add `LIMIT 200` if missing
   - Provide minutes CTE pattern
5) **Execute + repair loop**:
   - If error, feed exact error + schema to fix
   - If 0 rows with filters, retry without filters
6) **Summarize results** in natural language

## 🔧 Troubleshooting

### Connection Issues
1. **Run diagnostics**: `python test_connections.py`
2. **Check DB_URL format**: Must include `sslmode=require` for Neon
3. **Verify credentials**: Ensure your Neon connection string is correct

### Common Issues
1. **API Key**: Ensure `OPENAI_API_KEY` is set in `.env`  
2. **Dependencies**: Install all packages: `pip install -r requirements.txt`
3. **Empty results**: Run ingestion first: `python ingest_postgres.py --reset`
4. **HTML parsing**: Ensure `fsvarchiv/` directory exists with season folders

### Neon-Specific
- **SSL required**: Neon requires `sslmode=require` in connection string
- **Connection limits**: Neon free tier has connection limits
- **Timeouts**: Long ingestion may timeout; consider batching

## 🎯 Next Steps

- Add query history
- Implement query result caching
- Add data visualization for results
- Support for more complex analytical queries