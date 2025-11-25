/**
 * SQL guardrails for AI-generated queries
 * - Enforces single SELECT/CTE statement
 * - Blocks access to system catalogs
 * - Injects a safe LIMIT if missing
 */

const BLOCKED_PATTERNS = [
  /\bpg_catalog\b/i,
  /\binformation_schema\b/i,
  /\bpg_toast\b/i,
  /\bpg_stat\b/i,
  /\bpg_auth\b/i,
  /\bpg_locks\b/i,
  /\bpg_user\b/i,
];

const BLOCKED_FUNCTIONS = [/\bpg_sleep\s*\(/i];

const WRITE_COMMANDS = /\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b/i;

const HAS_LIMIT = /\blimit\s+\d+/i;
const HAS_FETCH_FIRST = /\bfetch\s+(first|next)\s+\d+\s+rows\b/i;

// Tables/views that AI queries are allowed to read
const ALLOWED_TABLES = new Set(
  [
    // Football data tables
    'teams',
    'players',
    'matches',
    'goals',
    'cards',
    'match_lineups',
    'match_substitutions',
    'match_coaches',
    'match_referees',
    'match_notes',
    'seasons',
    'season_competitions',
    'season_matchdays',
    'season_squads',
    'competitions',
    'coaches',
    'coach_careers',
    'player_careers',
    'player_aliases',
    'referees',
    // Materialized views (if any)
    'mainz_match_results',
    'player_career_stats',
    'season_performance',
    'competition_statistics',
    // Quiz / chat support tables
    'quiz_categories',
    'quiz_games',
    'quiz_rounds',
    'quiz_questions',
    'quiz_answers',
    'quiz_players',
    'quiz_generation_jobs',
    'chat_sessions',
    'chat_messages',
  ].map((t) => t.toLowerCase())
);

// Rough extractor for table names in FROM/JOIN clauses
// Excludes CTE names defined in WITH clauses
const extractTables = (sql: string): string[] => {
  // Extract CTE names from WITH clauses
  const cteNames = new Set<string>();
  const ctePattern = /\bwith\s+(?:recursive\s+)?([a-zA-Z0-9_]+)/gi;
  let cteMatch;
  while ((cteMatch = ctePattern.exec(sql)) !== null) {
    cteNames.add(cteMatch[1].toLowerCase());
  }
  
  // Also extract subsequent CTE names after commas in WITH clause
  const multiCtePattern = /,\s*([a-zA-Z0-9_]+)\s+as\s*\(/gi;
  let multiCteMatch;
  while ((multiCteMatch = multiCtePattern.exec(sql)) !== null) {
    cteNames.add(multiCteMatch[1].toLowerCase());
  }
  
  // Remove function calls to avoid false positives (e.g., EXTRACT(YEAR FROM column))
  let cleanedSql = sql;
  
  // Remove common date/time functions that use FROM keyword
  const functionPatterns = [
    /\bEXTRACT\s*\([^)]+\bFROM\s+[^)]+\)/gi,
    /\bSUBSTRING\s*\([^)]+\bFROM\s+[^)]+\)/gi,
    /\bTRIM\s*\([^)]+\bFROM\s+[^)]+\)/gi,
  ];
  
  for (const pattern of functionPatterns) {
    cleanedSql = cleanedSql.replace(pattern, '');
  }
  
  // Extract table names from FROM/JOIN clauses
  const matches = [...cleanedSql.matchAll(/\b(from|join)\s+([a-zA-Z0-9_\.]+)/gi)];
  return matches
    .map((m) => {
      const raw = m[2];
      // Strip schema prefix if present (e.g., public.table)
      const parts = raw.split('.');
      return parts[parts.length - 1].toLowerCase();
    })
    .filter((tableName) => !cteNames.has(tableName)); // Filter out CTE names
};

export class SqlValidationError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export interface ValidatedQuery {
  sql: string;
}

export const validateAndNormalizeSql = (rawSql: string): ValidatedQuery => {
  if (!rawSql || !rawSql.trim()) {
    throw new SqlValidationError('EMPTY_QUERY', 'Query is empty');
  }

  // Trim and drop a single trailing semicolon
  let sql = rawSql.trim();
  if (sql.endsWith(';')) {
    sql = sql.slice(0, -1).trimEnd();
  }

  // Reject multi-statement by checking any remaining semicolons
  if (sql.includes(';')) {
    throw new SqlValidationError('MULTI_STATEMENT', 'Only a single statement is allowed');
  }

  const upperSql = sql.toUpperCase();

  // Enforce SELECT/CTE entrypoint
  if (!(upperSql.startsWith('SELECT') || upperSql.startsWith('WITH'))) {
    throw new SqlValidationError('READ_ONLY_REQUIRED', 'Only SELECT/CTE queries are allowed');
  }

  // Block obvious write/DDL commands even if embedded in comments/strings
  if (WRITE_COMMANDS.test(sql)) {
    throw new SqlValidationError('WRITE_NOT_ALLOWED', 'Write or DDL statements are not allowed');
  }

  // Block system catalog access and dangerous functions
  for (const pattern of BLOCKED_PATTERNS) {
    if (pattern.test(sql)) {
      throw new SqlValidationError('SYSTEM_ACCESS_DENIED', 'Access to system catalogs is not allowed');
    }
  }

  for (const fn of BLOCKED_FUNCTIONS) {
    if (fn.test(sql)) {
      throw new SqlValidationError('FUNCTION_NOT_ALLOWED', 'This function is not allowed');
    }
  }

  // Allowlist tables in FROM/JOIN clauses
  const referencedTables = extractTables(sql);
  const disallowed = referencedTables.filter((t) => !ALLOWED_TABLES.has(t));
  if (disallowed.length > 0) {
    throw new SqlValidationError(
      'TABLE_NOT_ALLOWED',
      `Query references disallowed tables: ${Array.from(new Set(disallowed)).join(', ')}`
    );
  }

  // Inject a LIMIT if none present
  const hasLimit = HAS_LIMIT.test(sql) || HAS_FETCH_FIRST.test(sql);
  const normalizedSql = hasLimit ? sql : `${sql} LIMIT 200`;

  return { sql: normalizedSql };
};
