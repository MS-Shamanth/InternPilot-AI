import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '../../src/AppProviders';
import { createApplication, getApplicationsMeta } from '../../src/api/applications';
import { ApiError } from '../../src/api/client';
import { applyToJob, bookmarkJob, getJob, hideJob } from '../../src/api/jobs';
import { formatDateTime } from '../../src/lib/format';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';
import JobDetailPage from '../../src/pages/JobDetailPage';
import type { JobDetail } from '../../src/types/api';
import { APPLICATIONS_META, makeApplication, makeJob, makeJobDetail } from './jobFixtures';

vi.mock('../../src/api/jobs');
vi.mock('../../src/api/applications');

const getJobMock = vi.mocked(getJob);
const createApplicationMock = vi.mocked(createApplication);

const INTERVIEW_AT = '2025-02-10T14:30:00Z';

function renderPage(path = '/jobs/1') {
  render(
    <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE_FLAGS}>
      <AppProviders>
        <Routes>
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
          <Route path="/applications" element={<h1>Applications page</h1>} />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  );
  return { user: userEvent.setup() };
}

function serveJobDetail(overrides: Partial<JobDetail> = {}) {
  getJobMock.mockResolvedValue(makeJobDetail(overrides));
}

async function findTitle(title = 'Frontend Intern') {
  return screen.findByRole('heading', { level: 1, name: title });
}

beforeEach(() => {
  // Local noon, so "today" is 2025-01-20 in every time zone; only Date is faked.
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2025, 0, 20, 12));
  serveJobDetail();
  vi.mocked(getApplicationsMeta).mockResolvedValue(APPLICATIONS_META);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('JobDetailPage', () => {
  it('shows the match explanation and links to resume and interview prep when loaded', async () => {
    renderPage();
    const panel = await screen.findByRole('region', { name: 'MATCH SCORE: 72/100' });
    expect(within(panel).getByText('+ You have 1 of 2 required skills: React')).toBeInTheDocument();
    expect(within(panel).getByText('- Missing required skills: TypeScript')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Analyze your resume for this job' })).toHaveAttribute(
      'href',
      '/resume?jobId=1',
    );
    expect(screen.getByRole('link', { name: 'Interview prep for this job' })).toHaveAttribute(
      'href',
      '/interview/1',
    );
  });

  it('renders the title, facts, skills and description when the job loads', async () => {
    renderPage();
    expect(screen.getByRole('status', { busy: true })).toHaveTextContent('Loading job…');
    await findTitle();
    expect(getJobMock).toHaveBeenCalledWith(1, expect.any(AbortSignal));
    expect(screen.getByText('Example Labs · Berlin, Germany')).toBeInTheDocument();
    const overview = screen.getByRole('region', { name: 'Overview' });
    for (const [label, value] of [
      ['Work mode', 'Hybrid'],
      ['Employment type', 'Internship'],
      ['Experience level', 'Internship'],
      ['Minimum education', "Bachelor's"],
      ['Salary', '€1,500–€2,000 per month'],
      ['Source', 'Demo data'],
      ['Discovered', formatDateTime('2025-01-10T09:00:00Z')],
    ] as const) {
      expect(within(overview).getByText(label).nextElementSibling).toHaveTextContent(value);
    }
    expect(within(overview).getByText('Deadline').nextElementSibling).toHaveTextContent(
      'Feb 1, 2025 · 12 days left',
    );
    expect(screen.getByRole('list', { name: 'Required skills' })).toHaveTextContent(
      'Required: ReactRequired: TypeScript',
    );
    expect(screen.getByRole('list', { name: 'Preferred skills' })).toHaveTextContent(
      'Preferred: Testing Library',
    );
    const description = screen.getByText(/Build accessible UI\./);
    expect(description.textContent).toBe('Build accessible UI.\n\nWork with the design team.');
    expect(description).toHaveClass('whitespace-pre-line');
    expect(document.title).toBe('Frontend Intern · Jobs · InternPilot AI');
  });

  it('shows the description as literal text when it contains HTML', async () => {
    const html = '<script>alert("x")</script><b>Bold</b>';
    serveJobDetail({ description: html });
    renderPage();
    await findTitle();
    const region = screen.getByRole('region', { name: 'Description' });
    expect(within(region).getByText(html)).toBeInTheDocument();
    expect(region.querySelector('script, b')).toBeNull();
  });

  it('links to a real https application URL in a new tab with safe rel attributes', async () => {
    serveJobDetail({ source: 'remotive', application_url: 'https://remotive.com/jobs/42' });
    renderPage();
    await findTitle();
    const link = screen.getByRole('link', { name: /Apply on company site/ });
    expect(link).toHaveAttribute('href', 'https://remotive.com/jobs/42');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveTextContent('(opens in a new tab)');
  });

  it('shows a demo note and a similar-roles search when the job is a demo listing', async () => {
    renderPage();
    await findTitle();
    expect(screen.queryByRole('link', { name: /Apply on company site/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Demo listing: this sample company/)).toBeInTheDocument();
    const search = screen.getByRole('link', { name: /Search for similar roles/ });
    expect(search.getAttribute('href')).toMatch(/^https:\/\/www\.google\.com\/search\?q=/);
    expect(search).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('shows the demo note when a real source has a placeholder URL', async () => {
    serveJobDetail({ source: 'payload', application_url: 'https://careers.example.com/x' });
    renderPage();
    await findTitle();
    expect(screen.getByText(/Demo listing: this sample company/)).toBeInTheDocument();
  });

  it('renders no apply link when the application URL is not http(s)', async () => {
    serveJobDetail({ source: 'remotive', application_url: 'javascript:alert(1)' });
    renderPage();
    await findTitle();
    expect(screen.queryByRole('link', { name: /Apply on company site/ })).not.toBeInTheDocument();
    expect(screen.getByText('No valid application link was provided.')).toBeInTheDocument();
  });

  it('shows the indicators when the job is bookmarked and hidden', async () => {
    serveJobDetail({ is_bookmarked: true, is_hidden: true });
    renderPage();
    await findTitle();
    expect(screen.getByText('Bookmarked')).toBeInTheDocument();
    expect(screen.getByText('Hidden')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Bookmark/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Unhide' })).toBeInTheDocument();
  });

  it('shows the application details when the job is tracked', async () => {
    const application = {
      ...makeApplication(makeJob()),
      status: 'Interview' as const,
      deadline: '2025-02-05',
      interview_date: INTERVIEW_AT,
      recruiter_name: 'Alex Recruiter',
      recruiter_email: 'recruiter@example.com',
      notes: 'Prepare a portfolio walkthrough.',
      outcome: 'Waiting for feedback',
    };
    serveJobDetail({ application_status: 'Interview', application });
    const { user } = renderPage();
    await findTitle();
    const section = screen.getByRole('region', { name: 'Your application' });
    expect(within(section).getByText('Status: Interview')).toBeInTheDocument();
    const valueOf = (label: string) => within(section).getByText(label).nextElementSibling;
    expect(valueOf('Applied on')).toHaveTextContent('Jan 15, 2025');
    expect(valueOf('Application deadline')).toHaveTextContent(/^Feb 5, 2025/);
    expect(valueOf('Interview')).toHaveTextContent(formatDateTime(INTERVIEW_AT));
    // Local time with the zone named, e.g. "… 2:30 PM UTC" or "… 8:00 PM GMT+5:30".
    expect(formatDateTime(INTERVIEW_AT)).toMatch(/\d:\d{2} (AM|PM) \S+$/);
    expect(valueOf('Recruiter')).toHaveTextContent('Alex Recruiter');
    expect(within(section).getByRole('link', { name: 'recruiter@example.com' })).toHaveAttribute(
      'href',
      'mailto:recruiter@example.com',
    );
    expect(valueOf('Notes')).toHaveTextContent('Prepare a portfolio walkthrough.');
    expect(valueOf('Outcome')).toHaveTextContent('Waiting for feedback');
    expect(screen.queryByRole('button', { name: 'Save to tracker' })).not.toBeInTheDocument();
    await user.click(within(section).getByRole('link', { name: 'Manage in Applications' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Applications page' }),
    ).toBeInTheDocument();
  });

  it('saves an untracked job to the tracker with status Saved', async () => {
    createApplicationMock.mockResolvedValue({
      ...makeApplication(makeJob()),
      status: 'Saved',
      applied_at: null,
    });
    const { user } = renderPage();
    await findTitle();
    expect(screen.getByText(/Not tracked yet/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Save to tracker' }));
    expect(await screen.findByText('Saved "Frontend Intern" to your tracker')).toBeInTheDocument();
    expect(createApplicationMock).toHaveBeenCalledWith({ job_id: 1, status: 'Saved' });
  });

  it('shows the envelope message when saving to the tracker returns 409', async () => {
    createApplicationMock.mockRejectedValue(
      new ApiError('DUPLICATE_APPLICATION', 'This job is already in your tracker.', 409, null),
    );
    const { user } = renderPage();
    await findTitle();
    await user.click(screen.getByRole('button', { name: 'Save to tracker' }));
    expect(await screen.findByText('This job is already in your tracker.')).toBeInTheDocument();
  });

  it('bookmarks, hides and marks the job as applied through the API with toasts', async () => {
    vi.mocked(bookmarkJob).mockResolvedValue({ job_id: 1, is_bookmarked: true, is_hidden: false });
    vi.mocked(hideJob).mockResolvedValue({ job_id: 1, is_bookmarked: false, is_hidden: true });
    vi.mocked(applyToJob).mockResolvedValue(makeApplication(makeJob()));
    const { user } = renderPage();
    await findTitle();

    await user.click(screen.getByRole('button', { name: /Bookmark/ }));
    expect(await screen.findByText('Job bookmarked')).toBeInTheDocument();
    expect(bookmarkJob).toHaveBeenCalledWith(1);

    await user.click(screen.getByRole('button', { name: 'Hide' }));
    expect(
      await screen.findByText('Job hidden from lists and recommendations'),
    ).toBeInTheDocument();
    expect(hideJob).toHaveBeenCalledWith(1);

    await user.click(screen.getByRole('button', { name: 'Mark as applied' }));
    expect(await screen.findByText('Marked "Frontend Intern" as applied')).toBeInTheDocument();
    expect(applyToJob).toHaveBeenCalledWith(1);
    // Each mutation refetches the detail through the invalidation map.
    expect(getJobMock.mock.calls.length).toBeGreaterThanOrEqual(4);
  });

  it('disables Mark as applied when the status cannot move to Applied', async () => {
    serveJobDetail({
      application_status: 'Offer',
      application: { ...makeApplication(makeJob()), status: 'Offer' },
    });
    renderPage();
    await findTitle();
    const apply = await screen.findByRole('button', { name: 'Mark as applied' });
    await vi.waitFor(() => {
      expect(apply).toBeDisabled();
    });
  });

  it('shows Job not found when the API returns 404', async () => {
    getJobMock.mockRejectedValue(new ApiError('NOT_FOUND', 'Job not found.', 404, null));
    renderPage('/jobs/999');
    expect(await findTitle('Job not found')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to jobs' })).toHaveAttribute('href', '/jobs');
  });

  it.each(['abc', '0', '-1', '1.5', '99999999999999999999'])(
    'shows Job not found without fetching when the id is %s',
    async (id) => {
      renderPage(`/jobs/${id}`);
      expect(await findTitle('Job not found')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Back to jobs' })).toBeInTheDocument();
      expect(getJobMock).not.toHaveBeenCalled();
    },
  );

  it('shows an error state and reloads when Retry is clicked', async () => {
    getJobMock.mockRejectedValueOnce(new Error('offline'));
    const { user } = renderPage();
    expect(await screen.findByText('Could not load this job')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await findTitle()).toBeInTheDocument();
    expect(getJobMock).toHaveBeenCalledTimes(2);
  });
});
