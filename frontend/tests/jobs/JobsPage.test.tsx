import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getApplicationsMeta } from '../../src/api/applications';
import { ApiError } from '../../src/api/client';
import { applyToJob, bookmarkJob, hideJob, listJobs, unbookmarkJob } from '../../src/api/jobs';
import { ToastProvider } from '../../src/components/ui/toast/ToastProvider';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';
import JobsPage from '../../src/pages/JobsPage';
import { createTestQueryClient } from '../hooks/queryTestUtils';
import { APPLICATIONS_META, makeApplication, makeJob, makePage } from './jobFixtures';

vi.mock('../../src/api/jobs');
vi.mock('../../src/api/applications');

const listJobsMock = vi.mocked(listJobs);
const bookmarkJobMock = vi.mocked(bookmarkJob);
const unbookmarkJobMock = vi.mocked(unbookmarkJob);
const hideJobMock = vi.mocked(hideJob);
const applyToJobMock = vi.mocked(applyToJob);

const FRONTEND = makeJob();
const DATA = makeJob({
  id: 2,
  title: 'Data Analyst Intern',
  company: 'Northwind',
  application_status: 'Saved',
  is_bookmarked: true,
});

function CurrentSearch() {
  return <output aria-label="Current search">{useLocation().search}</output>;
}

function renderPage(initialSearch = '') {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/jobs${initialSearch}`]} future={ROUTER_FUTURE_FLAGS}>
          <JobsPage />
          <CurrentSearch />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { user: userEvent.setup() };
}

function card(title: string): HTMLElement {
  return screen.getByRole('article', { name: title });
}

beforeEach(() => {
  // Local noon, so "today" is 2025-01-20 in every time zone; only Date is faked.
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2025, 0, 20, 12));
  listJobsMock.mockResolvedValue(makePage([FRONTEND, DATA]));
  vi.mocked(getApplicationsMeta).mockResolvedValue(APPLICATIONS_META);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('JobsPage', () => {
  it('shows a skeleton, then job cards and an announced result count when jobs load', async () => {
    renderPage();
    expect(screen.getByRole('status', { busy: true })).toHaveTextContent('Loading jobs…');
    expect(await screen.findByRole('article', { name: 'Frontend Intern' })).toBeInTheDocument();
    expect(card('Frontend Intern')).toHaveTextContent('Deadline: Feb 1, 2025 · 12 days left');
    expect(card('Data Analyst Intern')).toHaveTextContent('Northwind');
    expect(screen.getByText('2 jobs found')).toHaveAttribute('aria-live', 'polite');
    expect(card('Frontend Intern')).toHaveTextContent('MATCH SCORE: 0/100');
  });

  it('calls listJobs with the params parsed from the URL', async () => {
    renderPage('?q=react&work_mode=remote&skills=React,SQL&sort=title&page=2&unknown=1');
    await screen.findByRole('article', { name: 'Frontend Intern' });
    expect(listJobsMock).toHaveBeenCalledWith(
      { q: 'react', work_mode: ['remote'], skills: ['React', 'SQL'], sort: 'title', page: 2 },
      expect.any(AbortSignal),
    );
  });

  it('requests the next page when Next is clicked', async () => {
    listJobsMock.mockImplementation((params = {}) =>
      Promise.resolve(
        makePage([params.page === 2 ? DATA : FRONTEND], {
          page: params.page ?? 1,
          total: 2,
          page_size: 1,
          total_pages: 2,
        }),
      ),
    );
    const { user } = renderPage('?page_size=1');
    await screen.findByRole('article', { name: 'Frontend Intern' });
    const pagination = screen.getByRole('navigation', { name: 'Pagination' });
    expect(pagination).toHaveTextContent('Page 1 of 2');
    expect(within(pagination).getByRole('button', { name: 'Previous' })).toBeDisabled();
    await user.click(within(pagination).getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('article', { name: 'Data Analyst Intern' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Pagination' })).toHaveTextContent('Page 2 of 2');
    expect(screen.getByText('Showing 2–2 of 2 jobs')).toBeInTheDocument();
    expect(listJobsMock).toHaveBeenLastCalledWith(
      { page: 2, page_size: 1 },
      expect.any(AbortSignal),
    );
    expect(screen.getByRole('status', { name: 'Current search' })).toHaveTextContent(
      '?page=2&page_size=1',
    );
  });

  it('bookmarks and removes bookmarks through the API with toasts', async () => {
    bookmarkJobMock.mockResolvedValue({ job_id: 1, is_bookmarked: true, is_hidden: false });
    unbookmarkJobMock.mockResolvedValue({ job_id: 2, is_bookmarked: false, is_hidden: false });
    const { user } = renderPage();
    await screen.findByRole('article', { name: 'Frontend Intern' });
    await user.click(within(card('Frontend Intern')).getByRole('button', { name: 'Bookmark' }));
    expect(await screen.findByText('Job bookmarked')).toBeInTheDocument();
    expect(bookmarkJobMock).toHaveBeenCalledWith(1);
    await user.click(within(card('Data Analyst Intern')).getByRole('button', { name: 'Bookmark' }));
    expect(await screen.findByText('Bookmark removed')).toBeInTheDocument();
    expect(unbookmarkJobMock).toHaveBeenCalledWith(2);
    expect(listJobsMock.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it('hides the job and explains how to see it again when Hide is clicked', async () => {
    hideJobMock.mockResolvedValue({ job_id: 1, is_bookmarked: false, is_hidden: true });
    const { user } = renderPage();
    await screen.findByRole('article', { name: 'Frontend Intern' });
    await user.click(within(card('Frontend Intern')).getByRole('button', { name: 'Hide' }));
    expect(
      await screen.findByText('Job hidden. Turn on "Include hidden jobs" to see it again.'),
    ).toBeInTheDocument();
    expect(hideJobMock).toHaveBeenCalledWith(1);
  });

  it('marks a job as applied and toasts with the job title', async () => {
    applyToJobMock.mockResolvedValue(makeApplication(DATA));
    const { user } = renderPage();
    await screen.findByRole('article', { name: 'Data Analyst Intern' });
    await user.click(
      within(card('Data Analyst Intern')).getByRole('button', { name: 'Mark as applied' }),
    );
    expect(await screen.findByText('Marked "Data Analyst Intern" as applied')).toBeInTheDocument();
    expect(applyToJobMock).toHaveBeenCalledWith(2);
  });

  it('shows the envelope message when marking as applied returns 409', async () => {
    applyToJobMock.mockRejectedValue(
      new ApiError('INVALID_STATUS_TRANSITION', 'Cannot move from Offer to Applied', 409, {
        from: 'Offer',
        to: 'Applied',
        allowed: ['Withdrawn'],
      }),
    );
    const { user } = renderPage();
    await screen.findByRole('article', { name: 'Frontend Intern' });
    await user.click(
      within(card('Frontend Intern')).getByRole('button', { name: 'Mark as applied' }),
    );
    expect(
      await screen.findByText('Cannot move from Offer to Applied. Allowed moves: Withdrawn.'),
    ).toBeInTheDocument();
  });

  it('disables Mark as applied when the transition table does not allow it', async () => {
    listJobsMock.mockResolvedValue(makePage([makeJob({ application_status: 'Offer' })]));
    renderPage();
    await screen.findByRole('article', { name: 'Frontend Intern' });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Mark as applied' })).toBeDisabled();
    });
  });

  it('offers Clear filters when filters match nothing', async () => {
    listJobsMock.mockResolvedValue(makePage([]));
    const { user } = renderPage('?q=nothing&sort=title');
    expect(await screen.findByText('No jobs match these filters')).toBeInTheDocument();
    expect(screen.getByText('No jobs found')).toBeInTheDocument();
    // One button in the filter panel, one in the empty state; use the empty state's.
    const [, emptyStateClear] = screen.getAllByRole('button', { name: 'Clear filters' });
    if (emptyStateClear === undefined) {
      throw new Error('Expected a Clear filters button in the empty state');
    }
    await user.click(emptyStateClear);
    expect(screen.getByRole('status', { name: 'Current search' })).toHaveTextContent('?sort=title');
  });

  it('explains how to import jobs when there are none at all', async () => {
    listJobsMock.mockResolvedValue(makePage([]));
    renderPage();
    expect(await screen.findByText('No jobs yet')).toBeInTheDocument();
    expect(screen.getByText('python -m app.cli ingest --source fixture')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Import/ })).not.toBeInTheDocument();
  });

  it('shows an error state and reloads when Retry is clicked', async () => {
    listJobsMock.mockRejectedValueOnce(
      new ApiError('VALIDATION_ERROR', 'The request is invalid.', 422, []),
    );
    const { user } = renderPage();
    expect(await screen.findByText('Could not load jobs')).toBeInTheDocument();
    expect(screen.getByText('The request is invalid.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('article', { name: 'Frontend Intern' })).toBeInTheDocument();
    expect(listJobsMock).toHaveBeenCalledTimes(2);
  });
});
