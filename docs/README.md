# FSV Mainz 05 Archive - Documentation Index

**Last Updated:** 2025-11-25

---

## 🎯 Quick Start

| Need | Document |
|------|----------|
| **Check database sync status** | [`DATABASE_SYNC_STATUS_FINAL.md`](DATABASE_SYNC_STATUS_FINAL.md) |
| **Understand schema differences** | [`SCHEMA_COMPARISON.md`](SCHEMA_COMPARISON.md) |
| **PostgreSQL schema reference** | [`SCHEMA_DOCUMENTATION_2025.md`](SCHEMA_DOCUMENTATION_2025.md) |
| **SQLite database info** | [`../DATABASE_README.md`](../DATABASE_README.md) |
| **Sync procedures** | [`SYNC_TO_POSTGRES.md`](SYNC_TO_POSTGRES.md) |

---

## 📚 Core Documentation

### Database Status & Sync
- **[DATABASE_SYNC_STATUS_FINAL.md](DATABASE_SYNC_STATUS_FINAL.md)** ⭐ **START HERE**
  - Complete sync status report (2025-11-25)
  - SQLite vs PostgreSQL comparison
  - Action items and pending tasks
  - Verification procedures

- **[SCHEMA_COMPARISON.md](SCHEMA_COMPARISON.md)** ⭐ **REFERENCE**
  - Side-by-side schema comparison
  - Differences explained
  - Use cases for each database

- **[SYNC_TO_POSTGRES.md](SYNC_TO_POSTGRES.md)**
  - Sync procedures and scripts
  - Current status (✅ Core data synced)
  - Manual sync methods

### Schema Documentation
- **[SCHEMA_DOCUMENTATION_2025.md](SCHEMA_DOCUMENTATION_2025.md)** ⭐ **DETAILED**
  - PostgreSQL schema (production)
  - All tables, indexes, views
  - Materialized views reference
  - Query examples

- **[../DATABASE_README.md](../DATABASE_README.md)**
  - SQLite database overview
  - Parser output details
  - Data quality metrics

### Implementation Guides
- **[PROFIREST_IMPLEMENTATION.md](PROFIREST_IMPLEMENTATION.md)**
  - Multi-match file parsing
  - 668 historical matches (1905-1960s)
  - Implementation details

- **[DATABASE_QUALITY_FINAL_REPORT.md](DATABASE_QUALITY_FINAL_REPORT.md)**
  - Data quality analysis
  - Coverage statistics
  - Known issues

### Performance
- **[MATERIALIZED_VIEWS_REFERENCE.md](MATERIALIZED_VIEWS_REFERENCE.md)**
  - View definitions
  - Refresh schedules
  - Performance gains (100-400x)

- **[PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md)**
  - Optimization history
  - Index strategies
  - Query performance

---

## 🔧 Development Guides

### Parser & Data Processing
- **[PARSER_FULL_NAME_FIX.md](PARSER_FULL_NAME_FIX.md)** - Name enrichment process
- **[PARSER_TEST_RESULTS.md](PARSER_TEST_RESULTS.md)** - Parser test results
- **[PARSER_IMPROVEMENTS.md](PARSER_IMPROVEMENTS.md)** - Parser evolution

### Data Quality
- **[DATABASE_QUALITY_TEST_REPORT.md](DATABASE_QUALITY_TEST_REPORT.md)** - Quality tests
- **[DUPLICATE_CARDS_FIX.md](DUPLICATE_CARDS_FIX.md)** - Duplicate handling
- **[VALIDATION_QUERIES.sql](VALIDATION_QUERIES.sql)** - Data validation queries

### Backend & API
- **[BACKEND_IMPLEMENTATION.md](BACKEND_IMPLEMENTATION.md)** - Backend architecture
- **[CHATBOT_DESIGN.md](CHATBOT_DESIGN.md)** - Chat system design
- **[EMBEDDINGS_DOCUMENTATION.md](EMBEDDINGS_DOCUMENTATION.md)** - Vector search

---

## 📊 Current Status

### Database Metrics

| Metric | SQLite | PostgreSQL | Synced |
|--------|--------|------------|--------|
| **Matches** | 3,956 | 3,956 | ✅ 100% |
| **Players** | 9,916 | 9,955 | ⚠️ 99.6% |
| **Coaches** | 566 | 566 | ✅ 100% |
| **Goals** | 8,312 | 8,312 | ✅ 100% |
| **Cards** | 5,768 | 5,768 | ✅ 100% |

### Pending Items
- ⏳ Sync 55 coach full names (run `python database/sync_now.py`)
- ⏳ Sync 241 player full names
- ⏳ Investigate player count discrepancy (+39 in PostgreSQL)

**Last Verified:** 2025-11-25

---

## 🎯 Quick Tasks

### Check Sync Status
```bash
cd /Users/christianau/Documents/02_Jobs/03_coding/playground/05app
python3 check_pg_status.py
```

### Sync Coach Names
```bash
python database/sync_now.py
```

### Verify Specific Data
```sql
-- Check Jürgen Klopp in PostgreSQL
psql $DB_URL -c "SELECT name, birth_date FROM coaches WHERE normalized_name LIKE '%klopp%';"
```

---

## 📁 File Organization

```
docs/
├── README.md                          ← YOU ARE HERE
├── DATABASE_SYNC_STATUS_FINAL.md     ← Sync status report
├── SCHEMA_COMPARISON.md               ← SQLite vs PostgreSQL
├── SCHEMA_DOCUMENTATION_2025.md       ← PostgreSQL schema
├── SYNC_TO_POSTGRES.md                ← Sync procedures
├── PROFIREST_IMPLEMENTATION.md        ← Historical matches
├── DATABASE_QUALITY_FINAL_REPORT.md   ← Data quality
├── MATERIALIZED_VIEWS_REFERENCE.md    ← Performance views
└── [other docs...]

../
├── DATABASE_README.md                 ← SQLite overview
├── check_pg_status.py                 ← Sync verification tool
└── database/
    ├── sync_now.py                    ← Coach name sync
    ├── final_postgres_sync.py         ← Full sync script
    └── backups/                       ← SQL dumps
```

---

## 🚀 Getting Started

### New Developers
1. Read **[DATABASE_SYNC_STATUS_FINAL.md](DATABASE_SYNC_STATUS_FINAL.md)**
2. Review **[SCHEMA_COMPARISON.md](SCHEMA_COMPARISON.md)**
3. Check **[BACKEND_IMPLEMENTATION.md](BACKEND_IMPLEMENTATION.md)**
4. Run `python3 check_pg_status.py` to verify setup

### Database Admins
1. Review **[SYNC_TO_POSTGRES.md](SYNC_TO_POSTGRES.md)**
2. Check **[SCHEMA_DOCUMENTATION_2025.md](SCHEMA_DOCUMENTATION_2025.md)**
3. Monitor sync with `check_pg_status.py`
4. Run `python database/sync_now.py` for name updates

### Data Analysts
1. Review **[SCHEMA_DOCUMENTATION_2025.md](SCHEMA_DOCUMENTATION_2025.md)**
2. Use **[VALIDATION_QUERIES.sql](VALIDATION_QUERIES.sql)** for examples
3. Check **[MATERIALIZED_VIEWS_REFERENCE.md](MATERIALIZED_VIEWS_REFERENCE.md)** for fast queries
4. See **[DATABASE_QUALITY_FINAL_REPORT.md](DATABASE_QUALITY_FINAL_REPORT.md)** for data coverage

---

## 📞 Support

For issues or questions:
1. Check relevant documentation above
2. Run `python3 check_pg_status.py` to verify current state
3. Review backup files in `database/backups/`
4. See recent changes in **[CHANGELOG.md](CHANGELOG.md)**

---

## 🔄 Recent Updates

**2025-11-25:**
- ✅ Created comprehensive sync status report
- ✅ Verified PostgreSQL sync (core data complete!)
- ✅ Identified pending name enrichment (55 coaches, 241 players)
- ✅ Updated all documentation with current status
- ✅ Created this documentation index

**2025-11-10:**
- ✅ Synced 668 profirest matches to PostgreSQL
- ✅ All match data now in both databases
- ✅ Coach name enrichment (77 with full names in SQLite)

**2025-11-09:**
- ✅ Added materialized views for performance
- ✅ Unique constraints to prevent duplicates
- ✅ Team consolidation (Mainz always team_id=1)

---

**Documentation Version:** 2025-11-25  
**Database Version:** 3,956 matches (complete)  
**Sync Status:** ✅ Core data synced, ⚠️ Names pending

