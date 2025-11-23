import { describe, expect, it } from 'vitest';
import { validateAndNormalizeSql, SqlValidationError } from '../../services/database/sql-validator.js';

describe('SQL Validator', () => {
  it('adds a LIMIT when missing', () => {
    const { sql } = validateAndNormalizeSql('select * from matches');
    expect(sql.toLowerCase()).toContain('limit 200');
  });

  it('respects existing limit', () => {
    const { sql } = validateAndNormalizeSql('select * from matches limit 10');
    expect(sql.toLowerCase()).toContain('limit 10');
    expect(sql.toLowerCase()).not.toContain('limit 200 limit');
  });

  it('rejects multi-statement queries', () => {
    expect(() => validateAndNormalizeSql('select 1; select 2')).toThrow(SqlValidationError);
  });

  it('rejects non-select queries', () => {
    expect(() => validateAndNormalizeSql('delete from matches')).toThrow(SqlValidationError);
  });

  it('rejects catalog access', () => {
    expect(() => validateAndNormalizeSql('select * from pg_catalog.pg_tables')).toThrow(
      SqlValidationError
    );
  });

  it('rejects dangerous functions', () => {
    expect(() => validateAndNormalizeSql('select pg_sleep(5)')).toThrow(SqlValidationError);
  });

  it('rejects disallowed tables', () => {
    expect(() => validateAndNormalizeSql('select * from pg_authid')).toThrow(SqlValidationError);
    expect(() => validateAndNormalizeSql('select * from secret_table')).toThrow(SqlValidationError);
  });

  it('allows whitelisted tables', () => {
    const { sql } = validateAndNormalizeSql('select * from public.matches');
    expect(sql.toLowerCase()).toContain('from public.matches');
  });
});
