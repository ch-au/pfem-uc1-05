import { z } from 'zod';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

// Load .env from project root
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = join(__dirname, '../../../..');
dotenv.config({ path: join(rootDir, '.env') });

const envSchema = z.object({
  // Server
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  API_PORT: z.string().default('8000').transform(Number),
  API_HOST: z.string().default('localhost'),

  // Database
  DATABASE_URL: z.string().url('Database URL is required'),

  // OpenRouter API (primary AI provider)
  OPENROUTER_API_KEY: z.string().min(1, 'OpenRouter API key is required'),
  OPENROUTER_MODEL: z.string().default('google/gemini-2.5-flash-preview-09-2025'),

  // Langfuse (optional - will use fallback prompts if not set)
  LANGFUSE_PUBLIC_KEY: z.string().optional(),
  LANGFUSE_SECRET_KEY: z.string().optional(),
  LANGFUSE_HOST: z.string().url().default('https://cloud.langfuse.com'),

  // Legacy (for compatibility with existing Python backend)
  OPENAI_API_KEY: z.string().optional(),
  ANTHROPIC_API_KEY: z.string().optional(),
  COHERE_API_KEY: z.string().optional(),
  GEMINI_API_KEY: z.string().optional(),
});

export type Env = z.infer<typeof envSchema>;

let parsedEnv: Env;

try {
  parsedEnv = envSchema.parse(process.env);
} catch (error) {
  if (error instanceof z.ZodError) {
    const missingVars = error.errors.map(e => `${e.path.join('.')}: ${e.message}`);
    console.error('❌ Environment validation failed:');
    console.error(missingVars.join('\n'));
    process.exit(1);
  }
  throw error;
}

export const env = parsedEnv;

// Helper to check if Langfuse is available
export const isLangfuseAvailable = () => {
  return !!(env.LANGFUSE_PUBLIC_KEY && env.LANGFUSE_SECRET_KEY);
};
