import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    setupFiles: ['./src/__tests__/setup.ts'],
    include: ['src/__tests__/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/__tests__/',
        'dist/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mockData',
      ],
    },
    testTimeout: 30000, // 30s für Integration Tests
    hookTimeout: 30000,
  },
  resolve: {
    alias: {
      '@': join(__dirname, './src'),
      '@tests': join(__dirname, './src/__tests__'),
    },
  },
});
