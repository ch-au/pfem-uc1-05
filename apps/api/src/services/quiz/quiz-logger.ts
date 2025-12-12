export interface QuizLogContext {
  gameId: string;
  roundNumber?: number;
  jobId?: string;
  traceId?: string;
  stage?: string;
}

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context: QuizLogContext;
  data?: Record<string, unknown>;
  error?: {
    message: string;
    code?: string;
    stack?: string;
  };
  duration_ms?: number;
}

class QuizLogger {
  private formatEntry(entry: LogEntry): string {
    const ctx = entry.context;
    const prefix = `[Quiz:${ctx.gameId?.slice(0, 8)}]`;
    const round = ctx.roundNumber ? `[R${ctx.roundNumber}]` : '';
    const stage = ctx.stage ? `[${ctx.stage}]` : '';
    const duration = entry.duration_ms ? ` (${entry.duration_ms}ms)` : '';
    
    return `${prefix}${round}${stage} ${entry.message}${duration}`;
  }

  private log(level: LogLevel, message: string, context: QuizLogContext, data?: Record<string, unknown>) {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      context,
      data,
    };

    const formatted = this.formatEntry(entry);
    
    switch (level) {
      case 'debug':
        console.debug(formatted, data ? JSON.stringify(data) : '');
        break;
      case 'info':
        console.log(formatted, data ? JSON.stringify(data) : '');
        break;
      case 'warn':
        console.warn(formatted, data ? JSON.stringify(data) : '');
        break;
      case 'error':
        console.error(formatted, data ? JSON.stringify(data) : '');
        break;
    }
  }

  debug(message: string, context: QuizLogContext, data?: Record<string, unknown>) {
    this.log('debug', message, context, data);
  }

  info(message: string, context: QuizLogContext, data?: Record<string, unknown>) {
    this.log('info', message, context, data);
  }

  warn(message: string, context: QuizLogContext, data?: Record<string, unknown>) {
    this.log('warn', message, context, data);
  }

  error(message: string, context: QuizLogContext, error?: Error, data?: Record<string, unknown>) {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level: 'error',
      message,
      context,
      data,
      error: error ? {
        message: error.message,
        code: (error as any).code,
        stack: error.stack?.substring(0, 500),
      } : undefined,
    };

    const formatted = this.formatEntry(entry);
    console.error(formatted, entry.error ? `\n  Error: ${entry.error.message}` : '');
    if (data) {
      console.error('  Data:', JSON.stringify(data));
    }
  }

  stageStart(stage: string, context: QuizLogContext) {
    this.info(`⏳ Starting: ${stage}`, { ...context, stage });
  }

  stageComplete(stage: string, context: QuizLogContext, duration_ms?: number) {
    const msg = duration_ms 
      ? `✓ Completed: ${stage} (${duration_ms}ms)`
      : `✓ Completed: ${stage}`;
    this.info(msg, { ...context, stage });
  }

  stageFailed(stage: string, context: QuizLogContext, error: Error, errorCode?: string) {
    this.error(`✗ Failed: ${stage}`, { ...context, stage }, error, { errorCode });
  }

  categorizeError(error: Error): { code: string; recoverable: boolean } {
    const msg = error.message.toLowerCase();
    
    if (msg.includes('does not exist') || msg.includes('column')) {
      return { code: 'SQL_COLUMN_ERROR', recoverable: false };
    }
    if (msg.includes('syntax error')) {
      return { code: 'SQL_SYNTAX_ERROR', recoverable: false };
    }
    if (msg.includes('relation')) {
      return { code: 'SQL_RELATION_ERROR', recoverable: false };
    }
    if (msg.includes('no results') || msg.includes('empty')) {
      return { code: 'SQL_NO_RESULTS', recoverable: false };
    }
    if (msg.includes('timeout') || msg.includes('timed out')) {
      return { code: 'TIMEOUT', recoverable: true };
    }
    if (msg.includes('rate limit') || msg.includes('429')) {
      return { code: 'RATE_LIMITED', recoverable: true };
    }
    if (msg.includes('network') || msg.includes('connection')) {
      return { code: 'NETWORK_ERROR', recoverable: true };
    }
    if (msg.includes('parse') || msg.includes('json')) {
      return { code: 'PARSE_ERROR', recoverable: true };
    }
    
    return { code: 'UNKNOWN', recoverable: true };
  }
}

export const quizLogger = new QuizLogger();
