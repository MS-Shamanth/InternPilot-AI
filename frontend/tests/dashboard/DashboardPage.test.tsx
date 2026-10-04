import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type * as Recharts from 'recharts';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '../../src/AppProviders';
import { ApiError } from '../../src/api/client';
import { getDashboard } from '../../src/api/dashboard';
import { formatDateTime } from '../../src/lib/format';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';
import DashboardPage from '../../src/pages/DashboardPage';
import type { Dashboard } from '../../src/types/api';
import {
  makeDashboard,
  makeEmptyDashboard,
  statusBreakdown,
  weeklyCounts,
} from './dashboardFixtures';

vi.mock('../../src/api/dashboard');

// jsdom has no layout (and no ResizeObserver), so render charts at a fixed size instead.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof Recharts>();
  const { cloneElement } = await import('react');
  return {
    ...actual,
    ResponsiveContainer: ({
      children,
    }: {
      children: ReactElement<{ width?: number; height?: number }>;
    }) => cloneElement(children, { width: 600, height: 280 }),
  };
});

const getDashboardMock = vi.mocked(getDashboard);

function serve(dashboard: Dashboard) {
  getDashboardMock.mockResolvedValue(dashboard);
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/dashboard']} future={ROUTER_FUTURE_FLAGS}>
      <AppProviders>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  );
  return { user: userEvent.setup() };
}

/** The `dd` value next to a stat's `dt` label. */
function statValue(label: string) {
  return screen.getByText(label, { selector: 'dt' }).nextElementSibling;
}

async function findRegion(name: string) {
  return screen.findByRole('region', { name });
}

beforeEach(() => {
  serve(makeDashboard());
});

describe('DashboardPage', () => {
  it('shows a loading skeleton when the dashboard is still loading', () => {
    getDashboardMock.mockReturnValue(new Promise(() => undefined));
    renderPage();
    expect(screen.getByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('status', { busy: true })).toHaveTextContent('Loading dashboard…');
  });

  it('renders every stat with its label when the dashboard loads', async () => {
    renderPage();
    await screen.findByText('Total jobs discovered');
    expect(getDashboardMock).toHaveBeenCalledWith(expect.any(AbortSignal));
    for (const [label, value] of [
      ['Total jobs discovered', '24'],
      ['Matching jobs', '9'],
      ['Applications submitted', '7'],
      ['Interviews scheduled', '2'],
      ['Offers received', '1'],
      ['Response rate', '42.9%'],
    ] as const) {
      expect(statValue(label)).toHaveTextContent(value);
    }
    expect(screen.getByText(/match score of 60 or more/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View applications' })).toHaveAttribute(
      'href',
      '/applications',
    );
  });

  it('formats the response rate with one decimal when the backend sends a whole number', async () => {
    serve(makeDashboard({ response_rate: 50 }));
    renderPage();
    await screen.findByText('Response rate');
    expect(statValue('Response rate')).toHaveTextContent('50.0%');
  });

  it('lists upcoming deadlines with job links, dates, days left and kind', async () => {
    renderPage();
    const region = await findRegion('Upcoming deadlines');
    const items = within(region).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    const [first, second] = items as [HTMLElement, HTMLElement];
    expect(within(first).getByRole('link', { name: 'Frontend Intern' })).toHaveAttribute(
      'href',
      '/jobs/7',
    );
    expect(first).toHaveTextContent('Example Labs');
    expect(first).toHaveTextContent('Feb 24, 2025 · Due today');
    expect(within(first).getByText('Application')).toBeInTheDocument();
    expect(within(second).getByRole('link', { name: 'Data Analyst Intern' })).toHaveAttribute(
      'href',
      '/jobs/12',
    );
    expect(second).toHaveTextContent('Due in 5 days');
    expect(within(second).getByText('Bookmark')).toBeInTheDocument();
    expect(within(second).getByText('Mar 1, 2025')).toHaveAttribute('datetime', '2025-03-01');
  });

  it('lists top recommendations with job links and backend scores', async () => {
    renderPage();
    const region = await findRegion('Top recommendations');
    expect(within(region).getByRole('link', { name: 'Backend Intern' })).toHaveAttribute(
      'href',
      '/jobs/21',
    );
    expect(region).toHaveTextContent('Example Cloud · Remote');
    expect(within(region).getByText('MATCH SCORE: 87/100')).toBeInTheDocument();
  });

  it('summarizes the score distribution chart in text when there are scored jobs', async () => {
    renderPage();
    const region = await findRegion('Match score distribution');
    expect(
      within(region).getByRole('img', {
        name: 'Jobs by match score: 0-19 2, 20-39 5, 40-59 8, 60-79 6, 80-100 3.',
      }),
    ).toBeInTheDocument();
  });

  it('lists recent activity with type labels and timestamps', async () => {
    renderPage();
    const region = await findRegion('Recent activity');
    const items = within(region).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    const [first] = items as [HTMLElement];
    expect(first).toHaveTextContent('Status changed');
    expect(first).toHaveTextContent('Moved Frontend Intern to Interview');
    expect(within(first).getByText(formatDateTime('2025-02-23T10:15:00Z'))).toHaveAttribute(
      'datetime',
      '2025-02-23T10:15:00Z',
    );
    expect(items[1]).toHaveTextContent('Bookmarked Data Analyst Intern');
  });

  it('shows the status breakdown numbers in a data table when it is expanded', async () => {
    const { user } = renderPage();
    const region = await findRegion('Status breakdown');
    expect(
      within(region).getByRole('img', {
        name: 'Applications by status: Saved 3, Interested 0, Applied 4, Assessment 0, Interview 2, Rejected 0, Offer 1, Withdrawn 0.',
      }),
    ).toBeInTheDocument();
    const toggle = within(region).getByRole('button', { name: 'Show data table' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(region).queryByRole('table')).not.toBeInTheDocument();

    await user.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(toggle).toHaveTextContent('Hide data table');
    const rows = within(within(region).getByRole('table')).getAllByRole('row').slice(1);
    expect(rows.map((row) => row.textContent)).toEqual([
      'Saved3',
      'Interested0',
      'Applied4',
      'Assessment0',
      'Interview2',
      'Rejected0',
      'Offer1',
      'Withdrawn0',
    ]);
  });

  it('shows the weekly application numbers in a data table when it is expanded', async () => {
    const { user } = renderPage();
    const region = await findRegion('Applications over time');
    expect(within(region).getByRole('img').getAttribute('aria-label')).toContain(
      'Week of Feb 17, 2025, 3 applications',
    );
    await user.click(within(region).getByRole('button', { name: 'Show data table' }));
    const table = within(region).getByRole('table');
    expect(within(table).getByRole('rowheader', { name: 'Week of Jan 13, 2025' })).toBeVisible();
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => row.lastElementChild?.textContent)).toEqual([
      '0',
      '1',
      '0',
      '2',
      '0',
      '1',
      '3',
      '0',
    ]);
  });

  it('shows the dashboard empty state with next actions when there is no data', async () => {
    serve(makeEmptyDashboard());
    renderPage();
    expect(
      await screen.findByRole('heading', { name: 'Your dashboard is empty' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Complete your profile' })).toHaveAttribute(
      'href',
      '/profile',
    );
    expect(screen.getByRole('link', { name: 'Browse jobs' })).toHaveAttribute('href', '/jobs');
    expect(screen.queryByText('Total jobs discovered')).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Status breakdown' })).not.toBeInTheDocument();
  });

  it('shows section empty states when jobs exist but nothing is tracked yet', async () => {
    serve(
      makeEmptyDashboard({
        total_jobs_discovered: 12,
        status_breakdown: statusBreakdown(),
        applications_over_time: weeklyCounts(),
      }),
    );
    renderPage();
    const deadlines = await findRegion('Upcoming deadlines');
    expect(
      within(deadlines).getByRole('heading', { name: 'No deadlines in the next 14 days' }),
    ).toBeInTheDocument();
    expect(within(deadlines).getByRole('link', { name: 'Browse jobs' })).toHaveAttribute(
      'href',
      '/jobs',
    );
    const activity = screen.getByRole('region', { name: 'Recent activity' });
    expect(within(activity).getByRole('heading', { name: 'No activity yet' })).toBeInTheDocument();
    expect(within(activity).getByRole('link', { name: 'Save your first job' })).toHaveAttribute(
      'href',
      '/jobs',
    );
    const breakdown = screen.getByRole('region', { name: 'Status breakdown' });
    expect(within(breakdown).getByText('No tracked applications yet')).toBeInTheDocument();
    expect(within(breakdown).queryByRole('img')).not.toBeInTheDocument();
    const overTime = screen.getByRole('region', { name: 'Applications over time' });
    expect(
      within(overTime).getByText('No applications submitted in the last 8 weeks'),
    ).toBeInTheDocument();
    expect(statValue('Total jobs discovered')).toHaveTextContent('12');
    expect(statValue('Response rate')).toHaveTextContent('0.0%');
  });

  it('shows an error state and loads the dashboard when Retry is clicked', async () => {
    getDashboardMock.mockRejectedValueOnce(new ApiError('NOT_FOUND', 'Not Found', 404, null));
    const { user } = renderPage();
    const title = await screen.findByText('Could not load the dashboard');
    expect(title.closest('[role="alert"]')).toHaveTextContent('Not Found');

    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('Total jobs discovered')).toBeInTheDocument();
    expect(getDashboardMock).toHaveBeenCalledTimes(2);
  });
});
