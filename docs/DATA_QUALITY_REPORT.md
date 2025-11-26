# FSV Mainz 05 Archive - Data Quality Report

**Generated:** 2025-11-26
**Database:** PostgreSQL (Neon)
**Status:** Production Ready with Known Issues

---

## Executive Summary

| Metric | Value | Status |
|--------|-------|--------|
| **Total Matches** | 3,956 | OK |
| **Total Players** | 9,916 | OK |
| **Total Coaches** | 566 | OK |
| **Total Teams** | 585 | OK |
| **Total Goals** | 8,312 | OK |
| **Total Cards** | 5,768 | OK |
| **Embeddings** | 11,067 | OK |

---

## Data Quality Metrics

### 1. Player Names

| Metric | Count | Percentage |
|--------|-------|------------|
| **Players with full names** (space in name) | 1,910 | 19.3% |
| **Players with only surnames** | 8,006 | 80.7% |
| **Invalid/parsing artifacts** | 23 | 0.2% |

**Notable players with full names:**
- JÜRGEN KLOPP (birth: 1967-06-16)
- ANDRÉ SCHÜRRLE
- All modern (post-2000) Bundesliga players

**Invalid entries (parsing artifacts):**
```
- "Die Aufstellung des FC liegt nicht vor."
- "Tor 3. 0:1 Ringel"
- Similar entries where HTML parsing captured error messages
```

**Root Cause:** Historical match pages (pre-1990) often don't link to player profiles, making full name extraction impossible. Invalid entries are error messages from the source HTML that were incorrectly parsed as player names.

**Recommendation:** These cannot be fixed automatically. Manual curation or data enrichment from external sources (e.g., transfermarkt.de) would be needed.

---

### 2. Coach Names

| Metric | Count | Percentage |
|--------|-------|------------|
| **Coaches with full names** | 77 | 13.6% |
| **Coaches with only surnames** | 489 | 86.4% |

**Root Cause:** Coach profiles are less frequently linked in the source archive.

---

### 3. Match Dates

| Era | Matches | Notes |
|-----|---------|-------|
| Pre-1920 | 64 | Historical, some approximate dates |
| 1920-1949 | 443 | Good coverage |
| 1950-1979 | 1,203 | Good coverage |
| 1980-1999 | 903 | Complete |
| 2000+ | 1,117 | Complete |
| **No date** | 226 | 5.7% - mostly historical |

**Root Cause:** Very early matches (1905-1920s) often have only year/month information, not exact dates.

---

### 4. Competition Coverage

| Competition | Matches |
|-------------|---------|
| Freundschaftsspiele (Friendlies) | 725 |
| Bundesliga | 652 |
| 2. Bundesliga | 568 |
| Oberliga Südwest | 408 |
| Amateur-Oberliga Südwest | 384 |
| Regionalliga Südwest | 342 |
| DFB-Pokal | 182 |

**Coverage:** All major competitions from 1905-2025 included.

---

### 5. Referential Integrity

| Check | Result |
|-------|--------|
| Goals without scorer | 0 |
| Lineups without player | 0 |
| Matches without teams | 0 |
| Duplicate players (same normalized_name) | 0 |

**Status:** All foreign key relationships are valid.

---

## Known Issues

### Issue 1: Parsing Artifacts in Players Table
- **Count:** 23 entries
- **Impact:** Low (0.2% of players)
- **Examples:** "Die Aufstellung des FC liegt nicht vor."
- **Recommendation:** Mark as `is_valid = false` or delete if not referenced

### Issue 2: Limited Full Name Coverage
- **Count:** 8,006 players without full names
- **Impact:** Medium - affects search/display quality
- **Recommendation:** Enrich from external data sources

### Issue 3: Missing Dates
- **Count:** 226 matches (5.7%)
- **Impact:** Low - mostly pre-1920 matches
- **Recommendation:** Historical research or accept as limitation

---

## Data Validation Queries

### Klopp Career Verification
```sql
SELECT name, total_matches, wins, draws, losses, goals, assists
FROM mv_player_career_stats
WHERE normalized_name LIKE '%klopp%';
```

**Result:**
| name | matches | wins | draws | losses | goals | assists |
|------|---------|------|-------|--------|-------|---------|
| JÜRGEN KLOPP | 431 | 181 | 112 | 142 | 62 | 33 |

### Schürrle Career Verification
```sql
SELECT name, total_matches, wins, draws, losses, goals
FROM mv_player_career_stats
WHERE normalized_name LIKE '%schurrle%';
```

---

## Semantic Search Test

**Query:** Find players similar to "Klopp"
```sql
SELECT name, 1 - (name_embedding <=> ref.embedding) as similarity
FROM players, (SELECT name_embedding as embedding FROM players WHERE name = 'JÜRGEN KLOPP') ref
ORDER BY name_embedding <=> ref.embedding
LIMIT 5;
```

**Result:** Embeddings working correctly for semantic search.

---

## Recommendations

### Priority 1 (Low effort, high value)
1. Create `is_valid` flag on players table to mark parsing artifacts
2. Add data quality view to exclude invalid entries from queries

### Priority 2 (Medium effort)
1. Enrich player names from transfermarkt.de API
2. Enrich coach names from Wikipedia/external sources

### Priority 3 (High effort)
1. Research exact dates for 226 undated matches
2. Manual review of all 23 parsing artifacts

---

## Database Health

| Component | Status |
|-----------|--------|
| PostgreSQL Schema | ✅ Complete |
| Data Sync | ✅ Complete (146,278 rows) |
| Cohere Embeddings | ✅ Complete (11,067) |
| HNSW Vector Indexes | ✅ Active |
| Materialized Views | ✅ 4 views created |
| Trigram Indexes | ✅ Active |

**Database is production-ready.**
