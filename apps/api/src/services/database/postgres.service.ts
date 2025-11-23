import pg from 'pg';
import { env } from '../../config/env.js';
import { validateAndNormalizeSql, SqlValidationError } from './sql-validator.js';

const { Pool } = pg;

export class PostgresService {
  private pool: pg.Pool;

  constructor() {
    this.pool = new Pool({
      connectionString: env.DATABASE_URL,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 10000,
    });

    // Handle pool errors
    this.pool.on('error', (err) => {
      console.error('Unexpected error on idle client', err);
    });

    console.log('✅ PostgreSQL connection pool initialized');
  }

  /**
   * Execute a query
   */
  async query<T extends pg.QueryResultRow = any>(text: string, params?: any[]): Promise<pg.QueryResult<T>> {
    const start = Date.now();
    try {
      const result = await this.pool.query<T>(text, params);
      const duration = Date.now() - start;

      if (env.NODE_ENV === 'development') {
        console.log(`📊 Query executed in ${duration}ms:`, text.substring(0, 100));
      }

      return result;
    } catch (error) {
      console.error('Database query error:', error);
      throw error;
    }
  }

  /**
   * Execute a query and return the first row
   */
  async queryOne<T extends pg.QueryResultRow = any>(text: string, params?: any[]): Promise<T | null> {
    const result = await this.query<T>(text, params);
    return result.rows[0] ?? null;
  }

  /**
   * Execute a query and return all rows
   */
  async queryMany<T extends pg.QueryResultRow = any>(text: string, params?: any[]): Promise<T[]> {
    const result = await this.query<T>(text, params);
    return result.rows;
  }

  /**
   * Execute SQL query for data retrieval (for AI-generated queries)
   * Includes safety checks and timeouts
   */
  async executeUserQuery(sql: string): Promise<{ rows: any[]; executionTimeMs: number }> {
    console.log(`🔍 [SQL EXECUTION] Starting user query execution...`);
    console.log(`   Query (first 200 chars): ${sql.substring(0, 200)}...`);
    
    const { sql: safeSql } = validateAndNormalizeSql(sql);
    console.log(`   ✓ SQL validation passed`);

    const client = await this.pool.connect();
    try {
      await client.query('BEGIN READ ONLY');
      await client.query('SET LOCAL statement_timeout = 5000');
      console.log(`   ✓ Transaction started (READ ONLY, 5s timeout)`);

      const start = Date.now();
      console.log(`   ⏳ Executing query...`);
      const result = await client.query(safeSql);
      const executionTimeMs = Date.now() - start;

      await client.query('COMMIT');
      console.log(`   ✓ Query executed successfully in ${executionTimeMs}ms`);
      console.log(`   ✓ Returned ${result.rows.length} row(s)`);
      if (result.rows.length > 0) {
        console.log(`   First row: ${JSON.stringify(result.rows[0]).substring(0, 150)}...`);
      }

      return {
        rows: result.rows,
        executionTimeMs,
      };
    } catch (error) {
      await client.query('ROLLBACK');
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error(`   ❌ SQL Execution Failed: ${errorMsg}`);
      
      if (error instanceof SqlValidationError) {
        throw error;
      }
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Transaction support
   */
  async transaction<T>(callback: (client: pg.PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await callback(client);
      await client.query('COMMIT');
      return result;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.query('SELECT 1');
      return true;
    } catch (error) {
      console.error('Database health check failed:', error);
      return false;
    }
  }

  /**
   * Close all connections
   */
  async close(): Promise<void> {
    await this.pool.end();
    console.log('PostgreSQL connection pool closed');
  }
}

// Singleton instance
export const postgresService = new PostgresService();
