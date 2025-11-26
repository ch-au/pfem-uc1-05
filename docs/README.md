# FSV Mainz 05 Archive - Documentation

**Last Updated:** 2025-11-26

---

## Quick Links

| Document | Description |
|----------|-------------|
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Complete PostgreSQL schema reference |
| [DATA_QUALITY_REPORT.md](DATA_QUALITY_REPORT.md) | Data quality analysis |
| [CHATBOT_DESIGN.md](CHATBOT_DESIGN.md) | Chat system architecture |
| [BACKEND_IMPLEMENTATION.md](BACKEND_IMPLEMENTATION.md) | Backend API documentation |

---

## Database Status

**PostgreSQL (Neon):** Production Ready

| Metric | Count |
|--------|-------|
| Matches | 3,956 |
| Players | 9,916 |
| Coaches | 566 |
| Teams | 585 |
| Goals | 8,312 |
| Cards | 5,768 |
| Embeddings | 11,067 |
| Materialized Views | 4 |

**Features:**
- Cohere embeddings for semantic search (1536 dimensions)
- HNSW vector indexes for fast similarity queries
- Trigram indexes for fuzzy text search
- Materialized views for pre-computed statistics
- Chat session/message tables for app

---

## Scripts

| Script | Purpose |
|--------|---------|
| `database/001_create_schema.sql` | Create PostgreSQL schema |
| `database/002_materialized_views.sql` | Create materialized views |
| `database/sync_sqlite_to_postgres.py` | Sync SQLite → PostgreSQL |
| `database/generate_embeddings.py` | Generate Cohere embeddings |
| `parsing/comprehensive_fsv_parser.py` | Parse HTML archive to SQLite |

---

## Quick Commands

### Check Database Status
```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM matches;"
```

### Test Klopp Query
```sql
SELECT name, total_matches, wins, losses, goals
FROM mv_player_career_stats
WHERE normalized_name LIKE '%klopp%';
```

### Semantic Search
```sql
SELECT name, 1 - (name_embedding <=> ref.embedding) as similarity
FROM players,
     (SELECT name_embedding FROM players WHERE name = 'JÜRGEN KLOPP') ref
ORDER BY name_embedding <=> ref.embedding
LIMIT 5;
```

### Refresh Materialized Views
```sql
SELECT refresh_all_materialized_views();
```

---

## File Structure

```
docs/
├── README.md              ← This file
├── DATABASE_SCHEMA.md     ← PostgreSQL schema reference
├── DATA_QUALITY_REPORT.md ← Data quality analysis
├── CHATBOT_DESIGN.md      ← Chat system design
├── BACKEND_IMPLEMENTATION.md
├── CHANGELOG.md
└── VALIDATION_QUERIES.sql

database/
├── 001_create_schema.sql
├── 002_materialized_views.sql
├── sync_sqlite_to_postgres.py
├── generate_embeddings.py
└── backups/

parsing/
└── comprehensive_fsv_parser.py

archive/
└── old_docs_2025/         ← Archived documentation
```

---

## Recent Changes (2025-11-26)

- Created complete PostgreSQL schema with all 22 tables
- Synced 146,278 rows from SQLite to PostgreSQL
- Generated 11,067 Cohere embeddings (players, teams, coaches)
- Created 4 materialized views for performance
- Added chat session/message tables
- Cleaned up outdated documentation

---

**Database Version:** Complete (3,956 matches, 1905-2025)
**Documentation Version:** 2025-11-26
