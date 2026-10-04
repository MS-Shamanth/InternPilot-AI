import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import App from '../src/App';

describe('App', () => {
  it('shows the dashboard inside the shell when opened at the root URL', async () => {
    window.history.replaceState({}, '', '/');
    render(<App />);

    // The dashboard is a lazy chunk; its first import is slow when many workers are busy.
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }, { timeout: 15000 }),
    ).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/dashboard');
  });
});
