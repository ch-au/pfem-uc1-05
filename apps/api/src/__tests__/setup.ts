import { beforeAll, afterAll, afterEach } from 'vitest';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

// Load test environment variables
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = join(__dirname, '../../../..');

// Load .env.test or .env
dotenv.config({ path: join(rootDir, '.env.test') });
dotenv.config({ path: join(rootDir, '.env') });

// Set test environment
process.env.NODE_ENV = 'test';

// Global test setup
beforeAll(() => {
  console.log('🧪 Test suite starting...');
});

afterAll(() => {
  console.log('✅ Test suite completed');
});

// Clean up after each test
afterEach(() => {
  // Reset any mocks if needed
});
