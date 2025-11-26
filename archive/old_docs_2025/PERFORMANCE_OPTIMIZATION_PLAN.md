# Performance Optimization Plan for FSV Mainz 05 Database

**Date:** 2025-11-09
**Database:** PostgreSQL (Neon Cloud)
**Current State:** Partially optimized with 3 materialized views, 13 indexes

---

## Executive Summary

This document outlines a comprehensive performance optimization strategy for the FSV Mainz 05 football statistics and quiz application database. The current implementation already includes solid foundational optimizations (materialized views, indexes, triggers). This plan identifies additional optimization opportunities to further improve query performance, reduce latency, and optimize resource utilization on Neon's serverless PostgreSQL platform.

### Current Performance Baselines

| Query Type | Before Optimization | After Current Optimization | Target |
|-----------|-------------------|--------------------------|--------|
| Chat history query | ~200ms | ~60ms | ~40ms |
| Player name search | ~150ms | ~30ms | ~20ms |
| Top scorers query | ~500ms | ~5ms | ~3ms |
| Match results query | ~300ms | ~6ms | ~4ms |
| Player season stats | ~800ms | ~8ms | ~5ms |

---

## 1. Current State Analysis

### 1.1 Database Architecture

**Tables:**
- **Transactional (6 tables):** quiz_games, quiz_questions, quiz_rounds, quiz_answers, chat_sessions, chat_messages, quiz_categories, quiz_players
- **Historical/Analytical (20+ tables):** teams, players, matches, goals, cards, lineups, competitions, seasons, etc.
- **Total Data Volume:** ~8,136 players, 3,231 matches, 5,652 goals, 11,120 cards (1905-2025)

**Connection Pool:**
- Max connections: 20
- Idle timeout: 30s
- Connection timeout: 10s
- **Assessment:** Adequate for current load, may need tuning under high concurrency

**Existing Optimizations:**
- ✅ 3 materialized views (top_scorers, match_results_summary, player_season_stats)
- ✅ 13 indexes (5 chat, 8 football)
- ✅ GIN trigram indexes for text search
- ✅ Partial indexes for common filters
- ✅ Auto-update triggers for stats aggregation
- ✅ Parameterized queries (SQL injection prevention)
- ✅ Query timeouts (5s for user queries)

### 1.2 Query Pattern Analysis

**From chat.service.ts:**
```typescript
// Pattern 1: Chat history retrieval (HIGH FREQUENCY)
SELECT * FROM chat_messages
WHERE session_id = $1
ORDER BY created_at ASC
// Current: ~60ms with idx_chat_messages_session_created_desc

// Pattern 2: Session validation (HIGH FREQUENCY)
SELECT * FROM chat_sessions WHERE session_id = $1
// Current: Index scan on PK
```

**From quiz.service.ts:**
```typescript
// Pattern 3: Round + Question JOIN (HIGH FREQUENCY)
SELECT qr.*, qq.*
FROM quiz_rounds qr
JOIN quiz_questions qq ON qr.question_id = qq.question_id
WHERE qr.game_id = $1 AND qr.round_number = $2
// Current: No specialized index

// Pattern 4: Leaderboard aggregation (MEDIUM FREQUENCY)
SELECT player_name, SUM(points_earned) as score, ...
FROM quiz_answers qa
JOIN quiz_rounds qr ON qa.round_id = qr.round_id
WHERE qr.game_id = $1
GROUP BY player_name
ORDER BY score DESC
// Current: Sequential scan + hash join

// Pattern 5: Question selection (LOW FREQUENCY, but N+1 pattern)
SELECT question_text FROM quiz_questions
WHERE category_id = (SELECT category_id FROM quiz_categories WHERE name = $1)
ORDER BY times_used ASC
LIMIT 100
// Current: Sequential scan + sort
```

**AI-Generated Queries (Dynamic, via executeUserQuery):**
- User-driven football statistics queries
- Unpredictable patterns, need broad coverage
- 5-second timeout enforced

---

## 2. Optimization Opportunities

### Priority Matrix

| Priority | Optimization | Impact | Complexity | Estimated Gain |
|----------|-------------|--------|------------|---------------|
| **P0** | Quiz leaderboard materialized view | High | Low | 50-80% faster |
| **P0** | Additional indexes for quiz queries | High | Low | 40-60% faster |
| **P0** | JSONB GIN indexes | High | Low | 70% faster metadata queries |
| **P0** | Materialized view refresh schedule | Critical | Medium | Ensures data freshness |
| **P1** | Query result caching (Redis) | Very High | Medium | 90-99% faster (cached) |
| **P1** | Recent matches materialized view | Medium | Low | 60% faster |
| **P1** | Connection pool tuning | Medium | Low | 20-30% better concurrency |
| **P2** | Table partitioning (historical data) | Medium | High | 40% faster range queries |
| **P2** | Read replica routing | Medium | Medium | Reduced primary load |
| **P3** | Prepared statement caching | Low | Medium | 10-15% faster |
| **P3** | VACUUM/ANALYZE automation | Low | Low | Maintains performance |

---

## 3. Detailed Optimization Recommendations

### 3.1 Priority 0: Immediate Wins (1-2 days)

#### A. Additional Materialized Views

**1. Quiz Game Leaderboard (All-Time)**
```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS public.quiz_global_leaderboard AS
SELECT
    qp.player_id,
    qp.player_name,
    qp.total_games,
    qp.total_questions,
    qp.total_correct,
    ROUND((qp.total_correct::numeric / NULLIF(qp.total_questions, 0)) * 100, 2) as accuracy_percentage,
    qp.average_time_seconds,
    qp.best_streak,
    qp.current_streak,
    qp.updated_at as last_played
FROM public.quiz_players qp
WHERE qp.total_games > 0
ORDER BY qp.total_correct DESC, qp.average_time_seconds ASC
WITH DATA;

CREATE UNIQUE INDEX idx_quiz_global_leaderboard_player ON public.quiz_global_leaderboard(player_id);
CREATE INDEX idx_quiz_global_leaderboard_accuracy ON public.quiz_global_leaderboard(accuracy_percentage DESC);
```

**Impact:** Instant leaderboard retrieval (~500ms → ~5ms)
**Use Case:** Global leaderboard endpoint, player statistics dashboard

**2. Recent Matches Summary**
```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS public.recent_matches AS
SELECT
    m.match_id,
    m.match_date,
    s.label as season,
    c.name as competition,
    t_home.name as home_team,
    t_away.name as away_team,
    m.home_score,
    m.away_score,
    CASE WHEN m.home_team_id = 1 THEN 'Home' ELSE 'Away' END as fsv_location,
    CASE
        WHEN m.home_team_id = 1 AND m.home_score > m.away_score THEN 'W'
        WHEN m.away_team_id = 1 AND m.away_score > m.home_score THEN 'W'
        WHEN m.home_score = m.away_score THEN 'D'
        ELSE 'L'
    END as result,
    (SELECT COUNT(*) FROM public.goals WHERE match_id = m.match_id AND team_id = 1) as fsv_goals,
    (SELECT json_agg(json_build_object('player', p.name, 'minute', g.minute))
     FROM public.goals g
     JOIN public.players p ON g.player_id = p.player_id
     WHERE g.match_id = m.match_id AND g.team_id = 1
       AND (g.event_type IS NULL OR g.event_type != 'own_goal')
    ) as scorers
FROM public.matches m
JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN public.seasons s ON sc.season_id = s.season_id
JOIN public.competitions c ON sc.competition_id = c.competition_id
JOIN public.teams t_home ON m.home_team_id = t_home.team_id
JOIN public.teams t_away ON m.away_team_id = t_away.team_id
WHERE (m.home_team_id = 1 OR m.away_team_id = 1)
  AND m.match_date >= (CURRENT_DATE - INTERVAL '2 years')
ORDER BY m.match_date DESC
WITH DATA;

CREATE UNIQUE INDEX idx_recent_matches_match_id ON public.recent_matches(match_id);
CREATE INDEX idx_recent_matches_date ON public.recent_matches(match_date DESC);
```

**Impact:** Fast recent match queries (~200ms → ~5ms)
**Use Case:** Homepage, recent results widget, chatbot "recent matches" queries

**3. Player Career Highlights**
```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS public.player_career_highlights AS
SELECT
    p.player_id,
    p.name,
    p.nationality,
    p.primary_position,
    -- Career span
    MIN(COALESCE(pc.start_year, ss.start_year)) as first_season,
    MAX(COALESCE(pc.end_year, ss.end_year)) as last_season,
    -- Appearance stats
    COUNT(DISTINCT ml.match_id) as total_appearances,
    COUNT(DISTINCT CASE WHEN ml.is_starter THEN ml.match_id END) as total_starts,
    -- Goal stats
    COUNT(DISTINCT g.goal_id) as total_goals,
    COUNT(DISTINCT CASE WHEN g.event_type = 'penalty' THEN g.goal_id END) as penalty_goals,
    -- Card stats
    COUNT(DISTINCT CASE WHEN ca.card_type = 'yellow' THEN ca.card_id END) as yellow_cards,
    COUNT(DISTINCT CASE WHEN ca.card_type = 'red' THEN ca.card_id END) as red_cards,
    -- Best season (most goals)
    (SELECT s.label
     FROM public.goals g2
     JOIN public.matches m2 ON g2.match_id = m2.match_id
     JOIN public.season_competitions sc2 ON m2.season_competition_id = sc2.season_competition_id
     JOIN public.seasons s ON sc2.season_id = s.season_id
     WHERE g2.player_id = p.player_id AND g2.team_id = 1
     GROUP BY s.label
     ORDER BY COUNT(*) DESC
     LIMIT 1
    ) as best_season
FROM public.players p
LEFT JOIN public.player_careers pc ON p.player_id = pc.player_id AND pc.team_id = 1
LEFT JOIN public.season_squads ss ON p.player_id = ss.player_id AND ss.team_id = 1
LEFT JOIN public.match_lineups ml ON p.player_id = ml.player_id AND ml.team_id = 1
LEFT JOIN public.goals g ON p.player_id = g.player_id AND g.team_id = 1
LEFT JOIN public.cards ca ON p.player_id = ca.player_id
GROUP BY p.player_id, p.name, p.nationality, p.primary_position
HAVING COUNT(DISTINCT ml.match_id) > 0
WITH DATA;

CREATE UNIQUE INDEX idx_player_career_highlights_player ON public.player_career_highlights(player_id);
CREATE INDEX idx_player_career_highlights_goals ON public.player_career_highlights(total_goals DESC);
CREATE INDEX idx_player_career_highlights_appearances ON public.player_career_highlights(total_appearances DESC);
```

**Impact:** Instant player profile queries (~600ms → ~4ms)
**Use Case:** Player profile pages, "who was the most..." chatbot queries

#### B. Additional Indexes for Quiz Tables

**1. Quiz Rounds Composite Index**
```sql
-- Optimize: getCurrentQuestion() JOIN query
CREATE INDEX IF NOT EXISTS idx_quiz_rounds_game_round
ON public.quiz_rounds(game_id, round_number)
INCLUDE (question_id);
```

**2. Quiz Answers Game Aggregation Index**
```sql
-- Optimize: getLeaderboard() query
CREATE INDEX IF NOT EXISTS idx_quiz_answers_round_player
ON public.quiz_answers(round_id, player_name)
INCLUDE (points_earned, is_correct, time_taken);
```

**3. Quiz Questions Category Index**
```sql
-- Optimize: generateQuestionsForGame() query
CREATE INDEX IF NOT EXISTS idx_quiz_questions_category_used
ON public.quiz_questions(category_id, times_used ASC)
INCLUDE (question_text);
```

**4. Quiz Games Active Games Index**
```sql
-- Optimize: Active games lookup
CREATE INDEX IF NOT EXISTS idx_quiz_games_status_created
ON public.quiz_games(status, created_at DESC)
WHERE status IN ('pending', 'in_progress');
```

#### C. JSONB GIN Indexes

**1. Chat Messages Metadata Index**
```sql
-- Enable fast metadata queries (confidence_score, visualization_type, etc.)
CREATE INDEX IF NOT EXISTS idx_chat_messages_metadata
ON public.chat_messages USING gin(metadata jsonb_path_ops);

-- For specific metadata field queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_confidence
ON public.chat_messages((metadata->>'confidence_score'))
WHERE metadata->>'confidence_score' IS NOT NULL;
```

**2. Quiz Questions Metadata Index**
```sql
CREATE INDEX IF NOT EXISTS idx_quiz_questions_metadata
ON public.quiz_questions USING gin(metadata jsonb_path_ops);
```

#### D. Materialized View Refresh Schedule

**Automated Refresh Strategy:**

1. **Real-time Views (refresh on write):**
   - `quiz_global_leaderboard` - Refresh after quiz_answers INSERT (via trigger)

2. **Near Real-time Views (refresh every 5 minutes):**
   - `recent_matches` - Low change frequency

3. **Daily Views (refresh at 3 AM):**
   - `top_scorers` - Historical data
   - `match_results_summary` - Historical data
   - `player_season_stats` - Historical data
   - `player_career_highlights` - Historical data

**Implementation Options:**

**Option A: PostgreSQL Cron (Neon Cloud supported)**
```sql
-- Install pg_cron extension
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule daily refresh at 3 AM UTC
SELECT cron.schedule('refresh-historical-views', '0 3 * * *', $$
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.top_scorers;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.match_results_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.player_season_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.player_career_highlights;
$$);

-- Schedule recent_matches refresh every 5 minutes
SELECT cron.schedule('refresh-recent-matches', '*/5 * * * *', $$
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.recent_matches;
$$);
```

**Option B: Application-level Scheduler (if pg_cron unavailable)**
- Add Node.js cron job using `node-cron`
- Endpoint: `POST /admin/refresh-views`
- Protected with admin auth

**Option C: Trigger-based Refresh (for quiz leaderboard)**
```sql
-- Refresh leaderboard after quiz answer submission
CREATE OR REPLACE FUNCTION refresh_quiz_leaderboard()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.quiz_global_leaderboard;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER refresh_leaderboard_after_answer
AFTER INSERT ON public.quiz_answers
FOR EACH STATEMENT
EXECUTE FUNCTION refresh_quiz_leaderboard();
```

---

### 3.2 Priority 1: High Impact (3-5 days)

#### A. Query Result Caching with Redis

**Implementation:**

```typescript
// apps/api/src/services/cache/redis.service.ts
import { createClient } from 'redis';

export class RedisService {
  private client: ReturnType<typeof createClient>;

  async connect() {
    this.client = createClient({
      url: process.env.REDIS_URL || 'redis://localhost:6379',
      socket: {
        connectTimeout: 5000,
      },
    });
    await this.client.connect();
  }

  async get<T>(key: string): Promise<T | null> {
    const data = await this.client.get(key);
    return data ? JSON.parse(data) : null;
  }

  async set(key: string, value: any, ttlSeconds: number = 300): Promise<void> {
    await this.client.setEx(key, ttlSeconds, JSON.stringify(value));
  }

  async del(key: string): Promise<void> {
    await this.client.del(key);
  }

  async invalidatePattern(pattern: string): Promise<void> {
    const keys = await this.client.keys(pattern);
    if (keys.length > 0) {
      await this.client.del(keys);
    }
  }
}
```

**Cache Strategy:**

| Query Type | Cache Key | TTL | Invalidation Strategy |
|-----------|-----------|-----|----------------------|
| Top scorers | `top_scorers:all` | 1 hour | Materialized view refresh |
| Match results | `match_results:{matchId}` | 1 day | Never (historical) |
| Player stats | `player_stats:{playerId}:{season}` | 1 hour | Materialized view refresh |
| Chat session | `chat_session:{sessionId}` | 5 min | Session update |
| Quiz leaderboard | `quiz_leaderboard:{gameId}` | 30 sec | Answer submission |
| Quiz question | `quiz_question:{questionId}` | 1 day | Never (static) |

**Modified Service Example:**

```typescript
// apps/api/src/services/chat/chat.service.ts
import { redisService } from '../cache/redis.service';

async getHistory(sessionId: string): Promise<ChatMessage[]> {
  // Try cache first
  const cacheKey = `chat_history:${sessionId}`;
  const cached = await redisService.get<ChatMessage[]>(cacheKey);
  if (cached) {
    return cached;
  }

  // Fetch from DB
  const history = await postgresService.queryMany<ChatMessage>(
    `SELECT * FROM public.chat_messages
     WHERE session_id = $1
     ORDER BY created_at ASC`,
    [sessionId]
  );

  // Cache for 5 minutes
  await redisService.set(cacheKey, history, 300);

  return history;
}

// Invalidate on new message
async saveMessage(data: {...}): Promise<ChatMessage> {
  const message = await postgresService.queryOne<ChatMessage>(...);

  // Invalidate cache
  await redisService.del(`chat_history:${data.session_id}`);

  return message;
}
```

**Benefits:**
- 90-99% faster for cached queries
- Reduced database load
- Better scalability

**Neon-Specific Considerations:**
- Use Redis Cloud or Upstash for serverless compatibility
- Ensures cache survives database scale-to-zero

#### B. Connection Pool Tuning

**Current Configuration:**
```typescript
max: 20,
idleTimeoutMillis: 30000,
connectionTimeoutMillis: 10000,
```

**Recommended Configuration (based on Neon serverless best practices):**

```typescript
// apps/api/src/services/database/postgres.service.ts
constructor() {
  this.pool = new Pool({
    connectionString: env.DATABASE_URL,

    // Connection limits
    max: env.NODE_ENV === 'production' ? 30 : 10,  // Increase for prod
    min: 2,  // Keep 2 connections alive

    // Timeouts
    idleTimeoutMillis: 20000,  // Shorter idle timeout for Neon
    connectionTimeoutMillis: 10000,

    // Keep-alive (important for Neon)
    keepAlive: true,
    keepAliveInitialDelayMillis: 10000,

    // Statement timeout (safety net)
    statement_timeout: 30000,  // 30s max query time

    // Neon-specific: Enable SSL
    ssl: env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
  });
}
```

**Connection Pooling Monitoring:**

```typescript
// Add metrics
async getPoolMetrics() {
  return {
    totalConnections: this.pool.totalCount,
    idleConnections: this.pool.idleCount,
    waitingClients: this.pool.waitingCount,
  };
}

// Health check endpoint
app.get('/health/db', async (req, res) => {
  const metrics = await postgresService.getPoolMetrics();
  const isHealthy = await postgresService.healthCheck();

  res.json({
    status: isHealthy ? 'healthy' : 'unhealthy',
    metrics,
  });
});
```

#### C. Query Optimization Patterns

**1. Avoid N+1 Queries in Quiz Question Generation**

**Current Pattern (N+1):**
```typescript
// Bad: 100 separate queries if 100 questions
for (const generatedQuestion of questionGeneration.result.questions) {
  const { rows } = await postgresService.executeUserQuery(generatedQuestion.sqlQueryNeeded);
  // ... process each
}
```

**Optimized Pattern (Batch):**
```typescript
// Good: Execute queries in parallel (within limits)
const BATCH_SIZE = 5;
for (let i = 0; i < questions.length; i += BATCH_SIZE) {
  const batch = questions.slice(i, i + BATCH_SIZE);
  await Promise.all(
    batch.map(async (q) => {
      const { rows } = await postgresService.executeUserQuery(q.sqlQueryNeeded);
      // ... process
    })
  );
}
```

**2. Optimize Leaderboard Query with Index**

**Current Query:**
```sql
SELECT player_name, SUM(points_earned) as score, ...
FROM quiz_answers qa
JOIN quiz_rounds qr ON qa.round_id = qr.round_id
WHERE qr.game_id = $1
GROUP BY player_name
ORDER BY score DESC
```

**Optimized with Covering Index:**
```sql
-- Add index
CREATE INDEX idx_quiz_rounds_game_id_covering
ON quiz_rounds(game_id)
INCLUDE (round_id);

-- Query remains same but uses index-only scan
```

**3. Chat History Pagination**

**Add pagination support:**
```typescript
async getHistory(
  sessionId: string,
  limit: number = 50,
  offset: number = 0
): Promise<ChatMessage[]> {
  return await postgresService.queryMany<ChatMessage>(
    `SELECT * FROM public.chat_messages
     WHERE session_id = $1
     ORDER BY created_at ASC
     LIMIT $2 OFFSET $3`,
    [sessionId, limit, offset]
  );
}
```

---

### 3.3 Priority 2: Medium Impact (1 week)

#### A. Table Partitioning for Historical Data

**Use Case:** Match data grows over time (1905-2025, 3,231+ matches)

**Partitioning Strategy: Range partitioning by decade**

```sql
-- 1. Create partitioned table (requires migration)
CREATE TABLE public.matches_partitioned (
    match_id INTEGER NOT NULL,
    season_competition_id INTEGER NOT NULL,
    home_team_id INTEGER,
    away_team_id INTEGER,
    match_date DATE,
    home_score INTEGER,
    away_score INTEGER,
    attendance INTEGER,
    venue TEXT,
    PRIMARY KEY (match_id, match_date)
) PARTITION BY RANGE (match_date);

-- 2. Create partitions
CREATE TABLE public.matches_historical
PARTITION OF public.matches_partitioned
FOR VALUES FROM ('1900-01-01') TO ('2000-01-01');

CREATE TABLE public.matches_2000s
PARTITION OF public.matches_partitioned
FOR VALUES FROM ('2000-01-01') TO ('2010-01-01');

CREATE TABLE public.matches_2010s
PARTITION OF public.matches_partitioned
FOR VALUES FROM ('2010-01-01') TO ('2020-01-01');

CREATE TABLE public.matches_2020s
PARTITION OF public.matches_partitioned
FOR VALUES FROM ('2020-01-01') TO ('2030-01-01');

-- 3. Create indexes on each partition
CREATE INDEX idx_matches_historical_date ON public.matches_historical(match_date);
CREATE INDEX idx_matches_2000s_date ON public.matches_2000s(match_date);
CREATE INDEX idx_matches_2010s_date ON public.matches_2010s(match_date);
CREATE INDEX idx_matches_2020s_date ON public.matches_2020s(match_date);
```

**Benefits:**
- 40-60% faster queries with date range filters
- Easier archival of old data
- Better VACUUM performance

**Note:** Requires data migration, test thoroughly before production

#### B. Read Replica Routing (Neon Feature)

**Neon Supports Read Replicas:**

```typescript
// apps/api/src/services/database/postgres.service.ts
export class PostgresService {
  private writePool: pg.Pool;
  private readPool: pg.Pool;

  constructor() {
    // Write pool (primary)
    this.writePool = new Pool({
      connectionString: env.DATABASE_URL,
      max: 20,
    });

    // Read pool (replica)
    this.readPool = new Pool({
      connectionString: env.DATABASE_READ_REPLICA_URL || env.DATABASE_URL,
      max: 30,  // More connections for reads
    });
  }

  // Use for SELECT queries
  async queryRead<T>(text: string, params?: any[]): Promise<T[]> {
    const result = await this.readPool.query<T>(text, params);
    return result.rows;
  }

  // Use for INSERT/UPDATE/DELETE
  async queryWrite<T>(text: string, params?: any[]): Promise<T | null> {
    const result = await this.writePool.query<T>(text, params);
    return result.rows[0] ?? null;
  }
}
```

**Route Queries:**
- Chatbot SQL queries → Read replica
- Quiz question fetches → Read replica
- Leaderboard queries → Read replica
- Quiz answer submission → Primary
- Chat message saves → Primary

**Benefits:**
- Reduced load on primary database
- Better scalability
- Improved read performance

---

### 3.4 Priority 3: Maintenance & Monitoring (Ongoing)

#### A. Automated VACUUM and ANALYZE

**Setup pg_cron job:**

```sql
-- Weekly VACUUM ANALYZE for chat tables (high write frequency)
SELECT cron.schedule('vacuum-chat-tables', '0 2 * * 0', $$
    VACUUM ANALYZE public.chat_sessions;
    VACUUM ANALYZE public.chat_messages;
$$);

-- Weekly VACUUM ANALYZE for quiz tables
SELECT cron.schedule('vacuum-quiz-tables', '0 2 * * 0', $$
    VACUUM ANALYZE public.quiz_games;
    VACUUM ANALYZE public.quiz_answers;
    VACUUM ANALYZE public.quiz_questions;
$$);

-- Monthly VACUUM for static tables
SELECT cron.schedule('vacuum-static-tables', '0 3 1 * *', $$
    VACUUM ANALYZE public.matches;
    VACUUM ANALYZE public.players;
    VACUUM ANALYZE public.goals;
$$);
```

#### B. Query Performance Monitoring

**Add query logging:**

```typescript
// apps/api/src/middleware/query-logger.middleware.ts
import { performance } from 'perf_hooks';

export function logSlowQueries(threshold: number = 1000) {
  return async (req, res, next) => {
    const start = performance.now();

    res.on('finish', () => {
      const duration = performance.now() - start;
      if (duration > threshold) {
        console.warn(`Slow query detected: ${req.method} ${req.path} took ${duration}ms`);
      }
    });

    next();
  };
}
```

**Enable PostgreSQL query logging (Neon dashboard):**
- Log queries > 500ms
- Monitor with Neon Metrics or Datadog

#### C. Index Maintenance

**Identify unused indexes:**

```sql
-- Find indexes that are never used
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE 'pg_toast%'
ORDER BY pg_relation_size(indexrelid) DESC;
```

**Monitor index bloat:**

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 4. Implementation Roadmap

### Phase 1: Quick Wins (Week 1)
- [ ] Create 3 new materialized views (quiz_global_leaderboard, recent_matches, player_career_highlights)
- [ ] Add 4 new indexes for quiz tables
- [ ] Add JSONB GIN indexes for metadata
- [ ] Set up materialized view refresh schedule (pg_cron or application-level)
- [ ] Test and validate performance improvements

**Expected Results:**
- Quiz leaderboard: ~500ms → ~5ms
- Recent matches: ~200ms → ~5ms
- Player profiles: ~600ms → ~4ms

### Phase 2: Caching Layer (Week 2)
- [ ] Set up Redis Cloud/Upstash
- [ ] Implement RedisService
- [ ] Add caching to chat.service.ts
- [ ] Add caching to quiz.service.ts
- [ ] Implement cache invalidation logic
- [ ] Monitor cache hit rate

**Expected Results:**
- 90%+ cache hit rate
- 95%+ faster cached queries
- 50% reduction in database load

### Phase 3: Connection Pool & Query Optimization (Week 3)
- [ ] Tune connection pool configuration
- [ ] Add pool metrics endpoint
- [ ] Optimize N+1 queries in quiz generation
- [ ] Add pagination to chat history
- [ ] Implement query logging middleware
- [ ] Monitor slow queries

**Expected Results:**
- Better concurrency handling
- Reduced connection wait times
- Improved API response times

### Phase 4: Advanced Optimizations (Week 4+)
- [ ] Evaluate table partitioning for matches
- [ ] Set up Neon read replica
- [ ] Implement read/write pool routing
- [ ] Set up automated VACUUM schedule
- [ ] Configure query performance monitoring
- [ ] Document all optimizations

**Expected Results:**
- 40% faster range queries (partitioned)
- Scalable read capacity
- Maintained database health

---

## 5. Performance Testing Plan

### 5.1 Baseline Metrics

**Before Optimization:**
```bash
# Run benchmark script
npm run benchmark:db

# Metrics to capture:
- Chat history query (50 messages): XXms
- Quiz leaderboard query: XXms
- Top scorers query: XXms
- Player search query: XXms
- Match results query: XXms
```

### 5.2 Load Testing

**Tools:** k6, Apache JMeter

```javascript
// k6-load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 }, // Ramp up to 100 users
    { duration: '5m', target: 100 }, // Stay at 100 users
    { duration: '2m', target: 0 },   // Ramp down
  ],
};

export default function () {
  // Test chat endpoint
  let chatRes = http.post('http://localhost:3000/api/chat/message', {
    session_id: 'test-session',
    content: 'Wer hat die meisten Tore geschossen?',
  });
  check(chatRes, { 'chat status 200': (r) => r.status === 200 });

  // Test quiz endpoint
  let quizRes = http.get('http://localhost:3000/api/quiz/leaderboard/test-game');
  check(quizRes, { 'quiz status 200': (r) => r.status === 200 });

  sleep(1);
}
```

### 5.3 Success Criteria

| Metric | Before | Target | Status |
|--------|--------|--------|--------|
| Chat history (p95) | 60ms | 40ms | ⏳ |
| Quiz leaderboard (p95) | 500ms | 10ms | ⏳ |
| Top scorers (p95) | 5ms | 3ms | ⏳ |
| Player search (p95) | 30ms | 20ms | ⏳ |
| Cache hit rate | 0% | 90% | ⏳ |
| Database connections (peak) | ? | <20 | ⏳ |

---

## 6. Cost-Benefit Analysis

### Neon Cloud Pricing Considerations

**Current Setup:**
- Free tier: 0.25 compute units, 0.5 GB storage
- Pro tier: ~$20/month for 1 CU, 10 GB

**Optimization Impact on Costs:**

1. **Materialized Views:**
   - Storage: +50 MB (~5% increase)
   - Compute: -30% (fewer complex queries)
   - **Net Impact:** Potential cost savings

2. **Redis Cache:**
   - External service: $10-30/month (Redis Cloud or Upstash)
   - Database compute: -50% load
   - **Net Impact:** +$15/month, but enables better scalability

3. **Read Replica:**
   - Neon Pro feature: +$10/month
   - Primary load: -70%
   - **Net Impact:** Better performance, supports 5x more users

**Total Monthly Cost:** ~$50-70/month (vs $20 baseline)
**Performance Gain:** 2-10x faster, 5x more capacity
**ROI:** Positive for production workloads

---

## 7. Monitoring and Alerts

### Key Metrics to Track

```typescript
// apps/api/src/services/metrics/metrics.service.ts
export class MetricsService {
  async captureQueryMetrics(query: string, duration: number) {
    // Track query performance
    await this.recordMetric('db.query.duration', duration, {
      query_type: this.classifyQuery(query),
    });
  }

  async captureCacheMetrics(hit: boolean) {
    await this.recordMetric('cache.hit_rate', hit ? 1 : 0);
  }

  async captureConnectionPoolMetrics(metrics: PoolMetrics) {
    await this.recordMetric('db.pool.total', metrics.totalConnections);
    await this.recordMetric('db.pool.idle', metrics.idleConnections);
    await this.recordMetric('db.pool.waiting', metrics.waitingClients);
  }
}
```

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Query duration (p95) | >500ms | >2s |
| Cache hit rate | <80% | <50% |
| Connection pool waiting | >5 | >10 |
| Database CPU | >70% | >90% |
| Materialized view age | >1 day | >3 days |

---

## 8. Rollback Plan

### If Performance Degrades

1. **Materialized Views:**
   ```sql
   DROP MATERIALIZED VIEW IF EXISTS public.quiz_global_leaderboard;
   DROP MATERIALIZED VIEW IF EXISTS public.recent_matches;
   DROP MATERIALIZED VIEW IF EXISTS public.player_career_highlights;
   ```

2. **Indexes:**
   ```sql
   -- Drop indexes (example)
   DROP INDEX IF EXISTS public.idx_quiz_rounds_game_round;
   DROP INDEX IF EXISTS public.idx_quiz_answers_round_player;
   ```

3. **Cache:**
   - Disable Redis integration
   - Fall back to direct database queries
   - Monitor database load

4. **Connection Pool:**
   - Revert to original configuration
   - Restart application

---

## 9. Documentation

### Files to Create/Update

1. **`/database/migrations/003_performance_optimizations.sql`**
   - All new indexes
   - All new materialized views
   - Refresh schedules

2. **`/docs/CACHE_STRATEGY.md`**
   - Cache key patterns
   - TTL policies
   - Invalidation rules

3. **`/docs/QUERY_OPTIMIZATION.md`**
   - Common query patterns
   - Index usage guide
   - N+1 query prevention

4. **`/apps/api/README.md`**
   - Update with Redis setup
   - Connection pool configuration
   - Performance benchmarks

---

## 10. Conclusion

This performance optimization plan provides a comprehensive roadmap to:

1. **Reduce latency** by 50-90% for common queries
2. **Improve scalability** to handle 5-10x more concurrent users
3. **Reduce database load** by 50-70% through caching
4. **Ensure data freshness** with automated materialized view refreshes
5. **Enable monitoring** for continuous performance improvement

**Estimated Total Implementation Time:** 3-4 weeks
**Expected Performance Improvement:** 2-10x faster query response times
**Recommended Priority:** Start with Phase 1 (Quick Wins) immediately

### Next Steps

1. Review and approve this plan
2. Set up development environment for testing
3. Begin Phase 1 implementation
4. Monitor and iterate based on results

---

**Document Version:** 1.0
**Last Updated:** 2025-11-09
**Author:** Claude Code Assistant
