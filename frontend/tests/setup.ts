import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';

// `findBy*`/`waitFor` default to 1 s, which is too tight when the full suite runs on many workers.
configure({ asyncUtilTimeout: 5000 });

beforeEach(() => {
  // No test may reach a real server, whatever a local `.env` says: tests that render pages
  // without mocking `src/api/*` get the "not configured" error, and a stray `fetch` rejects.
  // `tests/api/client.test.ts` installs its own base URL and fetch stub on top of these.
  vi.stubEnv('VITE_API_BASE_URL', '');
  vi.stubGlobal('fetch', () =>
    Promise.reject(new TypeError('Network access is disabled in tests; mock src/api/* instead.')),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
