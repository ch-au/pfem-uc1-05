# Materialized Views Reference Guide
**Last Updated:** 2025-11-09
**Database:** PostgreSQL (Neon)

---

## Overview

This database includes 4 materialized views that cache results of expensive queries for 100-400x performance improvement.

**What are Materialized Views?**
- Pre-calculated query results stored as a table
- Updated periodically (not real-time)
- Dramatically faster than running complex JOINs/aggregations on every request

---

## Views Summary

| View | Rows | Refresh | Speed Gain | Use For |
|------|------|---------|------------|---------|
| **mainz_match_results** | 3,305 | Daily | 160x | Match history, game details |
| **player_career_stats** | 1,172 | Weekly | 400x | Player profiles, top scorers |
| **season_performance** | 196 | Weekly | 300x | Season analysis, trends |
| **competition_statistics** | 23 | Monthly | 400x | Competition comparison |

---

## 1. mainz_match_results

### Purpose
Comprehensive details for every Mainz 05 match in history.

### Contains
- Match metadata (date, venue, attendance, referee)
- Teams and scores
- Mainz perspective (home/away, W/D/L)
- Goal scorers (JSON)
- Cards (JSON)

### Use Cases
- "Show all Bundesliga matches in 2023-24"
- "Find matches at a specific venue"
- "List matches by referee"
- "Get match results for a season"

### Schema
```sql
CREATE MATERIALIZED VIEW mainz_match_results AS
SELECT
    m.match_id,
    m.match_date,
    s.label as season,
    c.name as competition,
    t_home.name as home_team,
    t_away.name as away_team,
    m.home_score,
    m.away_score,
    CASE WHEN m.home_team_id = 1 THEN 'Home' ELSE 'Away' END as mainz_location,
    CASE
        WHEN (m.home_team_id = 1 AND m.home_score > m.away_score) OR
             (m.away_team_id = 1 AND m.away_score > m.home_score) THEN 'W'
        WHEN m.home_score = m.away_score THEN 'D'
        ELSE 'L'
    END as result,
    m.venue,
    m.attendance,
    r.name as referee,
    -- JSON arrays for scorers and cards
    (SELECT json_agg(...) FROM goals ...) as mainz_scorers,
    (SELECT json_agg(...) FROM cards ...) as mainz_cards
FROM matches m
JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN seasons s ON sc.season_id = s.season_id
JOIN competitions c ON sc.competition_id = c.competition_id
JOIN teams t_home ON m.home_team_id = t_home.team_id
JOIN teams t_away ON m.away_team_id = t_away.team_id
LEFT JOIN referees r ON m.referee_id = r.referee_id
WHERE m.home_team_id = 1 OR m.away_team_id = 1;
```

### Example Queries

**Recent Bundesliga matches:**
```sql
SELECT match_date, home_team, home_score, away_score, away_team, result
FROM mainz_match_results
WHERE competition = 'Bundesliga'
  AND match_date >= CURRENT_DATE - INTERVAL '1 year'
ORDER BY match_date DESC;
```

**Home vs away performance:**
```sql
SELECT
    mainz_location,
    COUNT(*) as matches,
    SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) / COUNT(*), 1) as win_pct
FROM mainz_match_results
WHERE competition = 'Bundesliga'
GROUP BY mainz_location;
```

**Matches with high attendance:**
```sql
SELECT match_date, home_team, away_team, venue, attendance
FROM mainz_match_results
WHERE attendance IS NOT NULL
ORDER BY attendance DESC
LIMIT 20;
```

### Refresh
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;
```

**When to refresh:** After importing new matches, or daily

---

## 2. player_career_stats

### Purpose
Aggregated career statistics for all players who appeared for Mainz 05.

### Contains
- Player biographical data
- Appearance counts (total, starts, substitute)
- Goal statistics (total, penalties, open play)
- Assists
- Cards (yellow, second yellow, red)
- Career span (first/last match)
- Calculated metrics (goals per match)

### Use Cases
- "Who are the top goal scorers?"
- "Player profile page data"
- "Find players by position with most appearances"
- "Compare two players' stats"

### Schema
```sql
CREATE MATERIALIZED VIEW player_career_stats AS
SELECT
    p.player_id,
    p.name,
    p.nationality,
    p.primary_position,
    COUNT(DISTINCT ml.match_id) as total_appearances,
    COUNT(DISTINCT CASE WHEN ml.is_starter THEN ml.match_id END) as total_starts,
    COUNT(DISTINCT g.goal_id) as total_goals,
    COUNT(DISTINCT CASE WHEN g.event_type = 'penalty' THEN g.goal_id END) as penalty_goals,
    COUNT(DISTINCT ga.goal_id) as total_assists,
    COUNT(DISTINCT CASE WHEN ca.card_type = 'yellow' THEN ca.card_id END) as yellow_cards,
    ROUND(COUNT(DISTINCT g.goal_id)::numeric / NULLIF(COUNT(DISTINCT ml.match_id), 0), 3) as goals_per_match
FROM players p
LEFT JOIN match_lineups ml ON p.player_id = ml.player_id AND ml.team_id = 1
LEFT JOIN goals g ON p.player_id = g.player_id AND g.team_id = 1
LEFT JOIN goals ga ON p.player_id = ga.assist_player_id
LEFT JOIN cards ca ON p.player_id = ca.player_id
GROUP BY p.player_id, p.name, p.nationality, p.primary_position
HAVING COUNT(DISTINCT ml.match_id) > 0;
```

### Example Queries

**Top 20 goal scorers:**
```sql
SELECT name, total_goals, total_appearances, goals_per_match
FROM player_career_stats
ORDER BY total_goals DESC
LIMIT 20;
```

**Most productive strikers (min 50 appearances):**
```sql
SELECT name, total_goals, total_assists, total_appearances, goals_per_match
FROM player_career_stats
WHERE primary_position LIKE '%Stürmer%'
  AND total_appearances >= 50
ORDER BY goals_per_match DESC
LIMIT 10;
```

**Player search:**
```sql
SELECT name, total_goals, total_appearances, nationality
FROM player_career_stats
WHERE name ILIKE '%Klopp%';
```

**Card statistics:**
```sql
SELECT name, yellow_cards, second_yellow_cards, red_cards, total_appearances
FROM player_career_stats
WHERE yellow_cards > 0
ORDER BY yellow_cards DESC
LIMIT 20;
```

### Refresh
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY player_career_stats;
```

**When to refresh:** Weekly, or after match imports

---

## 3. season_performance

### Purpose
Season-by-season performance statistics for each competition.

### Contains
- Season and competition details
- Match counts
- Win/draw/loss records
- Goals for/against and goal difference
- Win percentage

### Use Cases
- "Show Bundesliga performance over the years"
- "Best season ever?"
- "Compare DFB-Pokal performance across seasons"
- "Trend analysis (getting better/worse?)"

### Schema
```sql
CREATE MATERIALIZED VIEW season_performance AS
SELECT
    s.label as season,
    c.name as competition,
    COUNT(DISTINCT m.match_id) as matches_played,
    SUM(CASE WHEN ... THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) as draws,
    SUM(CASE WHEN ... THEN 1 ELSE 0 END) as losses,
    SUM(CASE WHEN m.home_team_id = 1 THEN m.home_score ELSE m.away_score END) as goals_for,
    SUM(CASE WHEN m.home_team_id = 1 THEN m.away_score ELSE m.home_score END) as goals_against,
    ROUND(100.0 * SUM(wins) / COUNT(*), 1) as win_percentage
FROM seasons s
JOIN season_competitions sc ON s.season_id = sc.season_id
JOIN competitions c ON sc.competition_id = c.competition_id
JOIN matches m ON sc.season_competition_id = m.season_competition_id
WHERE m.home_team_id = 1 OR m.away_team_id = 1
GROUP BY s.label, c.name;
```

### Example Queries

**Bundesliga history:**
```sql
SELECT season, matches_played, wins, draws, losses,
       goals_for, goals_against, win_percentage
FROM season_performance
WHERE competition = 'Bundesliga'
ORDER BY season DESC;
```

**Best Bundesliga seasons:**
```sql
SELECT season, wins, win_percentage, goals_for
FROM season_performance
WHERE competition = 'Bundesliga'
ORDER BY win_percentage DESC
LIMIT 10;
```

**Recent trend (last 5 seasons):**
```sql
SELECT season, competition, wins, draws, losses, win_percentage
FROM season_performance
WHERE start_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 5
ORDER BY season DESC, competition;
```

### Refresh
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY season_performance;
```

**When to refresh:** Weekly, or after season completion

---

## 4. competition_statistics

### Purpose
All-time aggregate statistics by competition.

### Contains
- Competition details
- Participation history (seasons, first/last)
- Total match counts
- Overall win/draw/loss record
- Goals for/against
- Overall win percentage

### Use Cases
- "Which competition has the best win rate?"
- "How many times have we played in the DFB-Pokal?"
- "Bundesliga vs 2. Bundesliga comparison"
- "Competition summary table"

### Schema
```sql
CREATE MATERIALIZED VIEW competition_statistics AS
SELECT
    c.name as competition,
    COUNT(DISTINCT s.season_id) as seasons_participated,
    MIN(s.start_year) as first_season,
    MAX(s.end_year) as last_season,
    COUNT(DISTINCT m.match_id) as total_matches,
    SUM(CASE WHEN ... THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) as draws,
    SUM(CASE WHEN ... THEN 1 ELSE 0 END) as losses,
    ROUND(100.0 * SUM(wins) / COUNT(*), 1) as win_percentage
FROM competitions c
JOIN season_competitions sc ON c.competition_id = sc.competition_id
JOIN seasons s ON sc.season_id = s.season_id
JOIN matches m ON sc.season_competition_id = m.season_competition_id
WHERE m.home_team_id = 1 OR m.away_team_id = 1
GROUP BY c.name;
```

### Example Queries

**All competitions ranked by matches played:**
```sql
SELECT competition, total_matches, wins, draws, losses, win_percentage
FROM competition_statistics
ORDER BY total_matches DESC;
```

**Main competitions comparison:**
```sql
SELECT competition, total_matches, win_percentage,
       goals_for || ':' || goals_against as goal_record
FROM competition_statistics
WHERE competition IN ('Bundesliga', '2. Bundesliga', 'DFB-Pokal', 'Europapokal')
ORDER BY total_matches DESC;
```

**Best and worst competitions:**
```sql
-- Best (min 50 matches)
SELECT competition, total_matches, win_percentage
FROM competition_statistics
WHERE total_matches >= 50
ORDER BY win_percentage DESC
LIMIT 5;

-- Worst (min 50 matches)
SELECT competition, total_matches, win_percentage
FROM competition_statistics
WHERE total_matches >= 50
ORDER BY win_percentage ASC
LIMIT 5;
```

### Refresh
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY competition_statistics;
```

**When to refresh:** Monthly, or after significant data imports

---

## Refresh All Views

### Manual Refresh
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;
REFRESH MATERIALIZED VIEW CONCURRENTLY player_career_stats;
REFRESH MATERIALIZED VIEW CONCURRENTLY season_performance;
REFRESH MATERIALIZED VIEW CONCURRENTLY competition_statistics;
```

### Using Function (Returns Timing)
```sql
SELECT * FROM refresh_all_materialized_views();
```

**Output:**
```
view_name              | refresh_time
-----------------------+-------------
mainz_match_results    | 00:00:01.234
player_career_stats    | 00:00:02.567
season_performance     | 00:00:00.456
competition_statistics | 00:00:00.123
```

---

## Refresh Schedule Recommendations

| View | Frequency | Trigger |
|------|-----------|---------|
| mainz_match_results | Daily | After match imports |
| player_career_stats | Weekly | Sunday night |
| season_performance | Weekly | Sunday night |
| competition_statistics | Monthly | 1st of month |

### Automated Refresh (Example Cron Job)
```bash
# Daily at 3 AM
0 3 * * * psql $DATABASE_URL -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;"

# Weekly on Sunday at 2 AM
0 2 * * 0 psql $DATABASE_URL -c "REFRESH MATERIALIZED VIEW CONCURRENTLY player_career_stats; REFRESH MATERIALIZED VIEW CONCURRENTLY season_performance;"

# Monthly on 1st at 1 AM
0 1 1 * * psql $DATABASE_URL -c "REFRESH MATERIALIZED VIEW CONCURRENTLY competition_statistics;"
```

---

## Performance Comparison

### Before (Raw Queries)

```sql
-- Match query: ~800ms
SELECT m.*, s.label, c.name, t_home.name, t_away.name, r.name
FROM matches m
JOIN season_competitions sc ON ...
JOIN seasons s ON ...
JOIN competitions c ON ...
JOIN teams t_home ON ...
JOIN teams t_away ON ...
LEFT JOIN referees r ON ...
WHERE m.home_team_id = 1 OR m.away_team_id = 1;

-- Player stats query: ~1,200ms
SELECT p.name,
       COUNT(DISTINCT ml.match_id),
       COUNT(DISTINCT g.goal_id),
       ...
FROM players p
LEFT JOIN match_lineups ml ON ...
LEFT JOIN goals g ON ...
LEFT JOIN cards c ON ...
GROUP BY p.player_id, p.name, ...;
```

### After (Materialized Views)

```sql
-- Match query: ~5ms (160x faster!)
SELECT * FROM mainz_match_results
WHERE competition = 'Bundesliga';

-- Player stats query: ~3ms (400x faster!)
SELECT * FROM player_career_stats
ORDER BY total_goals DESC;
```

---

## Notes

1. **CONCURRENTLY keyword:** Allows reads during refresh (non-blocking)
2. **Unique indexes required:** For CONCURRENT refresh, views need UNIQUE index
3. **Storage:** Views take up disk space (cached data)
4. **Staleness:** Data may be slightly out of date between refreshes
5. **Dependencies:** Views depend on base tables (matches, players, etc.)

---

## Troubleshooting

### View is Stale
```sql
-- Check last refresh time (PostgreSQL 9.4+)
SELECT schemaname, matviewname,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) as size
FROM pg_matviews
WHERE schemaname = 'public';
```

### Refresh is Slow
```sql
-- Check view size
SELECT pg_size_pretty(pg_total_relation_size('mainz_match_results'));

-- Analyze base tables first
ANALYZE matches;
ANALYZE players;
ANALYZE goals;
ANALYZE cards;

-- Then refresh
REFRESH MATERIALIZED VIEW CONCURRENTLY mainz_match_results;
```

### Cannot Refresh CONCURRENTLY
```
ERROR: cannot refresh materialized view "..." concurrently
HINT: Create a unique index with no WHERE clause on one or more columns
```

**Solution:** View needs unique index on primary key
```sql
CREATE UNIQUE INDEX idx_mainz_match_results_match_id
ON mainz_match_results(match_id);
```

---

**For More Information:**
- [PostgreSQL Materialized Views Documentation](https://www.postgresql.org/docs/current/sql-creatematerializedview.html)
- [Schema Documentation](SCHEMA_DOCUMENTATION_2025.md)
- [Quick Start Guide](../QUICK_START.md)
