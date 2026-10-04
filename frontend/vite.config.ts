import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    // Form interaction tests type many characters; leave headroom under full-suite load.
    testTimeout: 20000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/components/**', 'src/lib/**'],
      thresholds: {
        lines: 60,
      },
    },
  },
});
