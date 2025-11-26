# FSV Mainz 05 Archive Database

Complete database of FSV Mainz 05 football club history (1905-2025) parsed from HTML archive.

## 📊 Database Overview

| Metric | Count | Details |
|--------|-------|---------|
| **Matches** | 3,956 | All competitions 1905-2025 |
| **Players** | 9,916 | 1,910 (19.3%) with full names |
| **Coaches** | 566 | 77 (13.6%) with full names |
| **Teams** | 585 | Club and national teams |
| **Goals** | 8,312 | With scorers and assists |
| **Cards** | 5,768 | Yellow and red cards |
| **Substitutions** | 10,080 | Player changes |
| **Lineups** | 93,302 | Player appearances |

## 🆕 Recent Improvements

### Profirest Matches (Nov 2025)
- ✅ Added **668 previously skipped friendly matches** (+16.9% of total)
- ✅ Multi-match file parsing implemented
- ✅ 99% success rate (only 2 files failed)
- 📄 See [docs/PROFIREST_IMPLEMENTATION.md](docs/PROFIREST_IMPLEMENTATION.md)

### Coach Name Enrichment (Nov 2025)
- ✅ Improved from 3.7% to 13.6% with full names (**3.7x improvement**)
- ✅ **JÜRGEN KLOPP** now includes full name + career data
- ✅ 56 coaches enriched with birth dates and places
- 🔧 Script: [database/enrich_coach_names.py](database/enrich_coach_names.py)

## 📁 Files

```
fsv_archive_complete.db (4.5 MB)          Current complete database
fsv_archive_complete_BEFORE_PROFIREST.db  Backup before profirest implementation
database/backups/                         SQL dumps and logs
```

## 🔍 Example Queries

### Jürgen Klopp as Player
```sql
SELECT
    COUNT(*) as matches,
    SUM(CASE WHEN (home.name LIKE '%Mainz%' AND m.home_score > m.away_score)
              OR (away.name LIKE '%Mainz%' AND m.away_score > m.home_score)
        THEN 1 ELSE 0 END) as wins
FROM match_lineups l
JOIN players p ON l.player_id = p.player_id
JOIN matches m ON l.match_id = m.match_id
JOIN teams home ON m.home_team_id = home.team_id
JOIN teams away ON m.away_team_id = away.team_id
WHERE p.normalized_name LIKE '%klopp%';
```
**Result:** 431 matches, 185 wins (42.9%)

### Jürgen Klopp as Coach
```sql
SELECT c.name, cc.team_name, cc.start_date, cc.end_date
FROM coaches c
JOIN coach_careers cc ON c.coach_id = cc.coach_id
WHERE c.normalized_name LIKE '%klopp%'
ORDER BY cc.start_date DESC;
```
**Result:**
- 1. FSV Mainz 05 (2001-2008)
- Borussia Dortmund (2008-2015)
- Liverpool FC (2015-2024)
- Global Sports Director RB (2025-)

### André Schürrle Career
```sql
SELECT COUNT(*) as matches
FROM match_lineups l
JOIN players p ON l.player_id = p.player_id
WHERE p.normalized_name LIKE '%schurrle%';
```
**Result:** 92 matches for Mainz 05

## 📚 Documentation

- **[DATABASE_QUALITY_FINAL_REPORT.md](docs/DATABASE_QUALITY_FINAL_REPORT.md)** - Complete quality analysis
- **[PROFIREST_IMPLEMENTATION.md](docs/PROFIREST_IMPLEMENTATION.md)** - Multi-match file parsing
- **[SYNC_TO_POSTGRES.md](docs/SYNC_TO_POSTGRES.md)** - PostgreSQL sync guide
- **[SCHEMA_DOCUMENTATION_2025.md](docs/SCHEMA_DOCUMENTATION_2025.md)** - Database schema reference

## 🔄 PostgreSQL Sync

The SQLite database is ready to sync to PostgreSQL (Neon):

```bash
# Option 1: Use sync script (recommended)
export DATABASE_URL="postgresql://..."
bash database/sync_complete.sh

# Option 2: CSV export/import
sqlite3 fsv_archive_complete.db -csv -header 'SELECT * FROM matches' > matches.csv
psql $DATABASE_URL -c "\COPY matches FROM 'matches.csv' CSV HEADER"

# Option 3: Python sync with schema mapping
python database/sync_to_postgres.py --dry-run
python database/sync_to_postgres.py
```

**Note:** Schema differences exist between SQLite and PostgreSQL. Review [SYNC_TO_POSTGRES.md](docs/SYNC_TO_POSTGRES.md) for details.

## 🛠️ Maintenance Scripts

| Script | Purpose |
|--------|---------|
| `parsing/comprehensive_fsv_parser.py` | Main parser (use `--seasons` for specific seasons) |
| `database/enrich_coach_names.py` | Update coach names from profiles |
| `database/sync_complete.sh` | Export and prepare for PostgreSQL |
| `database/sync_to_postgres.py` | Python sync script (template) |

## 🎯 Data Quality

### Excellent (>90%)
- ✅ Match dates: 94.3% (3,730/3,956)
- ✅ Match results: 100% (all matches have scores)
- ✅ Player names: Includes all important historical players

### Good (10-20%)
- ✅ Player full names: 19.3% (improved with profile enrichment)
- ✅ Coach full names: 13.6% (3.7x improvement)

### Known Issues
- ⚠️ 36 invalid player records from parsing errors
- ⚠️ 5.7% of matches lack exact dates (pre-1920 historical matches)
- ⚠️ Some opponent lineups missing in profirest matches

## 📞 Support

For issues or questions:
- Check documentation in `docs/`
- Review backup files in `database/backups/`
- Consult schema reference: `docs/SCHEMA_DOCUMENTATION_2025.md`

---

**Last Updated:** 2025-11-10
**Database Version:** Complete with profirest matches
**Parser Version:** comprehensive_fsv_parser.py (multi-match support)
