# Quick Start Guide - FSV Mainz 05 Database
**Updated:** 2025-11-09
**Status:** Production Ready ✅

---

## TL;DR - What Changed

**Before:** Your query returned 0 Bundesliga matches (wrong!)
**After:** Query returns 652 Bundesliga matches with 33.1% win rate (correct!)

**Cause:** Parser created two separate teams ("1. FSV Mainz 05" and "FSV")
**Fix:** Merged teams + updated parser + created fast materialized views

---

## Quick Queries (Use These!)

### 1. Get Bundesliga Win Rate
```sql
SELECT * FROM competition_statistics WHERE competition = 'Bundesliga';
```

**Result:**
```
competition | total_matches | wins | win_percentage
Bundesliga  | 652          | 216  | 33.1%
```

### 2. Recent Matches
```sql
SELECT match_date, home_team, home_score, away_score, away_team, result
FROM mainz_match_results
WHERE season = '2023-24' AND competition = 'Bundesliga'
ORDER BY match_date DESC
LIMIT 10;
```

### 3. Top Goal Scorers Ever
```sql
SELECT name, total_goals, total_appearances, goals_per_match
FROM player_career_stats
ORDER BY total_goals DESC
LIMIT 20;
```

### 4. Season Performance
```sql
SELECT season, wins, draws, losses, goals_for, goals_against, win_percentage
FROM season_performance
WHERE competition = 'Bundesliga'
ORDER BY start_year DESC
LIMIT 10;
```

---

## What's Available Now

### 4 Fast Materialized Views

1. **mainz_match_results** (3,305 matches)
   - All Mainz matches with full details
   - Use for: Match history, season reviews, opponent analysis

2. **player_career_stats** (1,172 players)
   - Aggregated player statistics
   - Use for: Top scorers, player profiles, career analysis

3. **season_performance** (196 seasons)
   - Season-by-season performance
   - Use for: Historical trends, competition comparison

4. **competition_statistics** (23 competitions)
   - All-time stats by competition
   - Use for: Win rates, participation history

**Speed:** 100-400x faster than raw queries!

---

## What Was Fixed

### ✅ Database (Migrations 004-007)
- Merged duplicate Mainz teams
- Added unique constraints
- Added foreign keys
- Created materialized views

### ✅ Parser (comprehensive_fsv_parser.py)
- Recognizes "FSV" as Mainz 05
- Won't create duplicates again
- Handles all historical name variations

---

## Common Tasks

### After Match Import
```bash
# Refresh views
psql $DATABASE_URL << EOF
REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;
REFRESH MATERIALIZED VIEW CONCURRENTLY player_career_stats;
REFRESH MATERIALIZED VIEW CONCURRENTLY season_performance;
EOF
```

### Check Database Health
```sql
-- Verify team consolidation
SELECT team_id, name, COUNT(*) as matches
FROM teams t
LEFT JOIN matches m ON t.team_id = m.home_team_id OR t.team_id = m.away_team_id
WHERE t.team_id = 1
GROUP BY t.team_id, t.name;
-- Should show: team_id = 1 with 3,354 matches

-- Verify views
SELECT COUNT(*) FROM mainz_match_results;  -- Should be 3,305
SELECT COUNT(*) FROM player_career_stats;  -- Should be ~1,172
```

---

## Documentation

- **Complete Reference:** [FINAL_SCHEMA_AND_OPTIMIZATIONS.md](FINAL_SCHEMA_AND_OPTIMIZATIONS.md)
- **Full Summary:** [COMPLETE_SUMMARY.md](COMPLETE_SUMMARY.md)
- **Next Steps:** [WHATS_NEXT.md](WHATS_NEXT.md)

---

## Troubleshooting

**Q: Query still returns 0 matches?**
```sql
-- Check if migration was applied
SELECT COUNT(*) FROM teams WHERE team_id = 31;
-- Should return 0 (team was merged)
```

**Q: Views are stale?**
```sql
-- Refresh all views
REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;
REFRESH MATERIALIZED VIEW CONCURRENTLY player_career_stats;
REFRESH MATERIALIZED VIEW CONCURRENTLY season_performance;
REFRESH MATERIALIZED VIEW CONCURRENTLY competition_statistics;
```

**Q: Need to re-run parser?**
```bash
# Parser is already fixed - just run it
python parsing/comprehensive_fsv_parser.py

# Then refresh views
psql $DATABASE_URL -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;"
```

---

## Success! ✅

- ✅ 652 Bundesliga matches (was 0)
- ✅ Queries 100-400x faster
- ✅ Parser fixed
- ✅ Everything documented

**You're all set!**
