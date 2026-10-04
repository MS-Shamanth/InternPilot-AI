import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { AppProviders } from '../../src/AppProviders';
import { AppRoutes } from '../../src/AppRoutes';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE_FLAGS}>
      <AppProviders>
        <AppRoutes />
      </AppProviders>
    </MemoryRouter>,
  );
}

/** Pages are lazy chunks; their first import is slow under coverage or when many workers are busy. */
function findPageHeading(name: string) {
  return screen.findByRole('heading', { level: 1, name }, { timeout: 15000 });
}

/** Make `matchMedia` report a narrow (below `md`) viewport. */
function stubNarrowScreen() {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: true,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

// Warm the lazy page modules once, so no single test pays for the cold import.
beforeAll(async () => {
  await Promise.all([
    import('../../src/pages/DashboardPage'),
    import('../../src/pages/JobsPage'),
    import('../../src/pages/JobDetailPage'),
    import('../../src/pages/ApplicationsPage'),
    import('../../src/pages/ResumePage'),
    import('../../src/pages/InterviewPage'),
    import('../../src/pages/ProfilePage'),
  ]);
}, 60000);

describe('AppRoutes', () => {
  it.each([
    ['/dashboard', 'Dashboard'],
    ['/jobs', 'Jobs'],
    ['/jobs/42', 'Job details'],
    ['/applications', 'Applications'],
    ['/applications?view=board', 'Applications'],
    ['/resume', 'Resume analysis'],
    ['/interview', 'Interview prep'],
    ['/interview/7', 'Interview prep'],
    ['/profile', 'Profile'],
  ])('renders the page heading when visiting %s', async (path, heading) => {
    renderAt(path);

    expect(await findPageHeading(heading)).toBeInTheDocument();
  });

  it('redirects to the dashboard when visiting the root path', async () => {
    renderAt('/');

    expect(await findPageHeading('Dashboard')).toBeInTheDocument();
  });

  it('shows the not-found page with a dashboard link when the route is unknown', async () => {
    const user = userEvent.setup();
    renderAt('/does-not-exist');

    expect(await findPageHeading('Page not found')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Back to Dashboard' }));

    expect(await findPageHeading('Dashboard')).toBeInTheDocument();
  });

  it('navigates to a section when its sidebar link is clicked', async () => {
    const user = userEvent.setup();
    renderAt('/dashboard');
    const nav = screen.getByRole('navigation', { name: 'Primary' });

    await user.click(within(nav).getByRole('link', { name: 'Profile' }));

    expect(await findPageHeading('Profile')).toBeInTheDocument();
  });
});

describe('AppShell', () => {
  it('marks the active section link with aria-current when on a child route', async () => {
    renderAt('/jobs/42');
    await findPageHeading('Job details');
    const nav = screen.getByRole('navigation', { name: 'Primary' });

    expect(within(nav).getByRole('link', { name: 'Jobs' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute(
      'aria-current',
    );
  });

  it('lists every section in the sidebar when rendered', () => {
    renderAt('/dashboard');
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    const labels = within(nav)
      .getAllByRole('link')
      .map((link) => link.textContent);

    expect(labels).toEqual([
      'Dashboard',
      'Jobs',
      'Applications',
      'Resume analysis',
      'Interview prep',
      'Profile',
    ]);
  });

  it('provides a skip link that targets the main landmark when rendered', () => {
    renderAt('/dashboard');

    const skipLink = screen.getByRole('link', { name: 'Skip to main content' });
    const main = screen.getByRole('main');
    expect(skipLink).toHaveAttribute('href', `#${main.id}`);
    expect(main).toHaveAttribute('tabindex', '-1');
  });

  it('shows the demo identity notice when rendered', () => {
    renderAt('/dashboard');

    expect(screen.getByText(/not real authentication/)).toBeInTheDocument();
  });

  it('sets the document title from the current section when navigating', async () => {
    renderAt('/resume');
    await findPageHeading('Resume analysis');

    expect(document.title).toBe('Resume analysis · InternPilot AI');
  });

  it('keeps the sidebar visible without a toggle when the screen is wide', () => {
    renderAt('/dashboard');

    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Menu' })).not.toBeInTheDocument();
  });

  it('toggles the sidebar and aria-expanded when the menu button is pressed on a narrow screen', async () => {
    stubNarrowScreen();
    const user = userEvent.setup();
    renderAt('/dashboard');
    const toggle = screen.getByRole('button', { name: 'Menu' });
    const sidebar = document.getElementById(toggle.getAttribute('aria-controls') ?? '');

    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(sidebar).not.toBeVisible();

    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(sidebar).toBeVisible();

    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(sidebar).not.toBeVisible();
  });

  it('closes the narrow sidebar when a link is chosen', async () => {
    stubNarrowScreen();
    const user = userEvent.setup();
    renderAt('/dashboard');
    const toggle = screen.getByRole('button', { name: 'Menu' });

    await user.click(toggle);
    await user.click(screen.getByRole('link', { name: 'Jobs' }));

    expect(await findPageHeading('Jobs')).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('closes the narrow sidebar and refocuses the toggle when Escape is pressed', async () => {
    stubNarrowScreen();
    const user = userEvent.setup();
    renderAt('/dashboard');
    const toggle = screen.getByRole('button', { name: 'Menu' });

    await user.click(toggle);
    await user.tab();
    await user.keyboard('{Escape}');

    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle).toHaveFocus();
  });
});
