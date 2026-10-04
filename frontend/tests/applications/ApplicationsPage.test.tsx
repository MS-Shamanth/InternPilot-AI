import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '../../src/AppProviders';
import {
  createApplication,
  deleteApplication,
  getApplicationsMeta,
  listApplications,
  updateApplication,
} from '../../src/api/applications';
import { ApiError } from '../../src/api/client';
import { listJobs } from '../../src/api/jobs';
import { dateTimeLocalToIso } from '../../src/lib/applicationForm';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';
import ApplicationsPage from '../../src/pages/ApplicationsPage';
import { APPLICATIONS_META, makeJob, makePage } from '../jobs/jobFixtures';
import { makeTrackedApplication } from './applicationFixtures';

vi.mock('../../src/api/applications');
vi.mock('../../src/api/jobs');

const listMock = vi.mocked(listApplications);

const TRACKED = makeTrackedApplication({
  id: 10,
  job_id: 1,
  status: 'Applied',
  notes: 'Old notes',
  recruiter_name: 'Alex Recruiter',
});
const SAVED = makeTrackedApplication({
  id: 11,
  job_id: 2,
  status: 'Saved',
  title: 'Data Intern',
  company: 'Acme Analytics',
  applied_at: null,
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
}

function renderPage(path = '/applications') {
  render(
    <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE_FLAGS}>
      <AppProviders>
        <ApplicationsPage />
        <LocationProbe />
      </AppProviders>
    </MemoryRouter>,
  );
  return { user: userEvent.setup() };
}

function search(): string {
  return screen.getByTestId('location').textContent ?? '';
}

async function findTable() {
  return screen.findByRole('table', { name: /Tracked applications/ });
}

function row(title: string): HTMLElement {
  const link = screen.getByRole('link', { name: title });
  const tableRow = link.closest('tr');
  if (tableRow === null) {
    throw new Error(`No row for ${title}`);
  }
  return tableRow;
}

beforeEach(() => {
  // Local noon, so "today" is 2025-01-20 in every time zone; only Date is faked.
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2025, 0, 20, 12));
  vi.mocked(getApplicationsMeta).mockResolvedValue(APPLICATIONS_META);
  listMock.mockResolvedValue([TRACKED, SAVED]);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ApplicationsPage', () => {
  it('syncs the selected view with ?view= and falls back to the table', async () => {
    const { user } = renderPage('/applications?view=bogus');
    await findTable();
    expect(screen.getByRole('tab', { name: 'Table' })).toHaveAttribute('aria-selected', 'true');

    await user.click(screen.getByRole('tab', { name: 'Board' }));
    expect(search()).toBe('?view=board');
    expect(await screen.findAllByRole('region')).toHaveLength(8);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Table' }));
    expect(search()).toBe('?view=table');
    expect(await findTable()).toBeInTheDocument();
  });

  it('opens the board when the URL asks for it', async () => {
    renderPage('/applications?view=board');
    expect(await screen.findByRole('region', { name: /^Saved\b/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Board' })).toHaveAttribute('aria-selected', 'true');
  });

  it('renders one row per application with links, badges and allowed status choices', async () => {
    renderPage();
    await findTable();
    const tracked = row('Frontend Intern');
    expect(within(tracked).getByRole('link', { name: 'Frontend Intern' })).toHaveAttribute(
      'href',
      '/jobs/1',
    );
    expect(within(tracked).getByText('Example Labs')).toBeInTheDocument();
    expect(within(tracked).getByText('Jan 15, 2025')).toBeInTheDocument();
    expect(tracked).toHaveTextContent('Feb 1, 2025 · 12 days left');
    const select = within(tracked).getByRole('combobox', { name: 'Status for Frontend Intern' });
    expect(
      within(select)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Applied', 'Assessment', 'Interview', 'Rejected', 'Offer', 'Withdrawn']);
    expect(within(row('Data Intern')).getAllByText('Not set')).toHaveLength(2);
  });

  it('moves an application with the row status select', async () => {
    vi.mocked(updateApplication).mockResolvedValue({ ...TRACKED, status: 'Interview' });
    const { user } = renderPage();
    await findTable();
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Status for Frontend Intern' }),
      'Interview',
    );
    expect(updateApplication).toHaveBeenCalledWith(10, { status: 'Interview' });
    expect(await screen.findByText('Moved Frontend Intern to Interview')).toBeInTheDocument();
  });

  it('writes the status filter to the URL and sends it to the API when statuses are checked', async () => {
    const { user } = renderPage('/applications?status=Offer&status=bogus');
    await findTable();
    expect(listMock).toHaveBeenCalledWith({ status: ['Offer'] }, expect.any(AbortSignal));
    expect(screen.getByRole('checkbox', { name: 'Offer' })).toBeChecked();

    await user.click(screen.getByRole('checkbox', { name: 'Applied' }));
    expect(search()).toBe('?status=Applied&status=Offer');
    await vi.waitFor(() => {
      expect(listMock).toHaveBeenCalledWith(
        { status: ['Applied', 'Offer'] },
        expect.any(AbortSignal),
      );
    });
  });

  it('shows an empty state that clears the filter when no application matches', async () => {
    listMock.mockImplementation((params = {}) =>
      Promise.resolve(params.status === undefined ? [TRACKED] : []),
    );
    const { user } = renderPage('/applications?status=Offer');
    expect(await screen.findByText('No applications with these statuses')).toBeInTheDocument();
    await user.click(screen.getAllByRole('button', { name: 'Clear status filter' })[0] as Element);
    expect(search()).toBe('');
    expect(await findTable()).toBeInTheDocument();
  });

  it('creates an application with the chosen job, status and details', async () => {
    vi.mocked(listJobs).mockResolvedValue(
      makePage([
        makeJob({ id: 1, application_status: 'Applied' }),
        makeJob({ id: 3, title: 'Design Intern', company: 'Pixel Co' }),
      ]),
    );
    vi.mocked(createApplication).mockResolvedValue(
      makeTrackedApplication({ id: 12, job_id: 3, title: 'Design Intern' }),
    );
    const { user } = renderPage();
    await findTable();
    await user.click(screen.getByRole('button', { name: 'Add application' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add application' });
    const jobSelect = await within(dialog).findByRole('combobox', { name: /^Job/ });
    expect(jobSelect).toHaveFocus();
    expect(listJobs).toHaveBeenCalledWith(
      { sort: 'title', page_size: 100 },
      expect.any(AbortSignal),
    );
    // Already-tracked jobs are not offered.
    expect(
      within(jobSelect)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Choose a job', 'Design Intern · Pixel Co']);

    await user.selectOptions(jobSelect, '3');
    await user.selectOptions(within(dialog).getByRole('combobox', { name: /^Status/ }), 'Applied');
    fireEvent.change(within(dialog).getByLabelText('Application deadline'), {
      target: { value: '2025-03-01' },
    });
    fireEvent.change(within(dialog).getByLabelText('Interview'), {
      target: { value: '2025-02-10T14:30' },
    });
    await user.type(within(dialog).getByLabelText('Notes'), 'Referred by a friend');
    await user.click(within(dialog).getByRole('button', { name: 'Add application' }));

    expect(createApplication).toHaveBeenCalledWith({
      job_id: 3,
      status: 'Applied',
      notes: 'Referred by a friend',
      deadline: '2025-03-01',
      interview_date: dateTimeLocalToIso('2025-02-10T14:30'),
    });
    expect(await screen.findByText('Added "Design Intern" to your tracker')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows the error inline and as a toast when the job is missing or already tracked', async () => {
    vi.mocked(listJobs).mockResolvedValue(makePage([makeJob({ id: 3, title: 'Design Intern' })]));
    vi.mocked(createApplication).mockRejectedValue(
      new ApiError('DUPLICATE_APPLICATION', 'This job is already in your tracker.', 409, null),
    );
    const { user } = renderPage();
    await findTable();
    await user.click(screen.getByRole('button', { name: 'Add application' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add application' });
    const jobSelect = await within(dialog).findByRole('combobox', { name: /^Job/ });

    await user.click(within(dialog).getByRole('button', { name: 'Add application' }));
    expect(createApplication).not.toHaveBeenCalled();
    expect(within(dialog).getByText('Choose a job to track.')).toBeInTheDocument();

    await user.selectOptions(jobSelect, '3');
    await user.click(within(dialog).getByRole('button', { name: 'Add application' }));
    expect(await screen.findAllByText('This job is already in your tracker.')).toHaveLength(2);
    expect(jobSelect).toHaveAttribute('aria-invalid', 'true');
    expect(jobSelect).toHaveFocus();
  });

  it('edits only the changed fields and sends null for cleared ones', async () => {
    vi.mocked(updateApplication).mockResolvedValue({ ...TRACKED, notes: 'New notes' });
    const { user } = renderPage();
    await findTable();
    await user.click(within(row('Frontend Intern')).getByRole('button', { name: /^Edit/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Edit application' });
    expect(within(dialog).queryByRole('combobox', { name: /^Status/ })).not.toBeInTheDocument();

    await user.clear(within(dialog).getByLabelText('Recruiter name'));
    const notes = within(dialog).getByLabelText('Notes');
    await user.clear(notes);
    await user.type(notes, 'New notes');
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));

    expect(updateApplication).toHaveBeenCalledWith(10, {
      recruiter_name: null,
      notes: 'New notes',
    });
    expect(await screen.findByText('Saved changes to "Frontend Intern"')).toBeInTheDocument();
  });

  it('shows 422 errors next to their fields when an edit is rejected', async () => {
    vi.mocked(updateApplication).mockRejectedValue(
      new ApiError('VALIDATION_ERROR', 'Request validation failed.', 422, [
        { loc: ['body', 'recruiter_email'], msg: 'value is not a valid email address', type: 'x' },
      ]),
    );
    const { user } = renderPage();
    await findTable();
    await user.click(within(row('Frontend Intern')).getByRole('button', { name: /^Edit/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Edit application' });
    const email = within(dialog).getByLabelText('Recruiter email');
    await user.type(email, 'not-an-email');
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));

    expect(
      await within(dialog).findByText('value is not a valid email address'),
    ).toBeInTheDocument();
    expect(email).toHaveAttribute('aria-invalid', 'true');
    expect(email).toHaveFocus();
    expect(screen.getByText('Request validation failed.')).toBeInTheDocument();
  });

  it('does not send a request when an edit changes nothing', async () => {
    const { user } = renderPage();
    await findTable();
    await user.click(within(row('Frontend Intern')).getByRole('button', { name: /^Edit/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Edit application' });
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(updateApplication).not.toHaveBeenCalled();
    expect(await screen.findByText('No changes to save')).toBeInTheDocument();
  });

  it('deletes after confirmation and toasts', async () => {
    vi.mocked(deleteApplication).mockResolvedValue(undefined);
    const { user } = renderPage();
    await findTable();
    await user.click(within(row('Frontend Intern')).getByRole('button', { name: /^Delete/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Delete application?' });
    expect(dialog).toHaveTextContent('“Frontend Intern” at Example Labs');
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();

    await user.click(within(dialog).getByRole('button', { name: 'Delete application' }));
    expect(deleteApplication).toHaveBeenCalledWith(10);
    expect(
      await screen.findByText('Deleted "Frontend Intern" from your tracker'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('cancels a delete without calling the API', async () => {
    const { user } = renderPage();
    await findTable();
    await user.click(within(row('Data Intern')).getByRole('button', { name: /^Delete/ }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(deleteApplication).not.toHaveBeenCalled();
  });

  it('shows an empty state with a link to jobs and the add action', async () => {
    listMock.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText('No applications yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Find jobs to track' })).toHaveAttribute(
      'href',
      '/jobs',
    );
    expect(screen.getAllByRole('button', { name: 'Add application' })).toHaveLength(2);
  });

  it('shows an error state and reloads when Retry is clicked', async () => {
    listMock.mockRejectedValueOnce(new Error('offline'));
    const { user } = renderPage();
    expect(await screen.findByText('Could not load applications')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await findTable()).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledTimes(2);
  });
});
