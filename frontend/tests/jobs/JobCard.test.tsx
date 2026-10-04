import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { JobCard } from '../../src/components/jobs/JobCard';
import type { JobAction } from '../../src/components/jobs/JobCard';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';
import type { MarkAppliedState } from '../../src/lib/markApplied';
import type { JobSummary } from '../../src/types/api';
import { makeJob } from './jobFixtures';

const AVAILABLE: MarkAppliedState = { available: true, reason: null };

interface RenderOptions {
  markApplied?: MarkAppliedState;
  pendingAction?: JobAction | null;
}

function renderCard(job: JobSummary, options: RenderOptions = {}) {
  const handlers = {
    onToggleBookmark: vi.fn(),
    onToggleHidden: vi.fn(),
    onMarkApplied: vi.fn(),
  };
  render(
    <MemoryRouter future={ROUTER_FUTURE_FLAGS}>
      <JobCard
        job={job}
        today="2025-01-20"
        markApplied={options.markApplied ?? AVAILABLE}
        pendingAction={options.pendingAction ?? null}
        {...handlers}
      />
    </MemoryRouter>,
  );
  return { ...handlers, user: userEvent.setup() };
}

describe('JobCard', () => {
  it('shows the job facts, a detail link, salary and deadline with days left', () => {
    renderCard(makeJob());
    const card = screen.getByRole('article', { name: 'Frontend Intern' });
    expect(within(card).getByRole('link', { name: 'Frontend Intern' })).toHaveAttribute(
      'href',
      '/jobs/1',
    );
    expect(card).toHaveTextContent('Example Labs · Berlin, Germany');
    const details = within(card).getByRole('list', { name: 'Job details' });
    expect(details).toHaveTextContent('Hybrid');
    expect(details).toHaveTextContent('Internship');
    expect(card).toHaveTextContent('€1,500–€2,000 per month');
    expect(card).toHaveTextContent('Deadline: Feb 1, 2025 · 12 days left');
    expect(card).toHaveTextContent('Source: Demo data');
  });

  it('says when salary and deadline are not listed', () => {
    renderCard(makeJob({ salary_min: null, salary_max: null, deadline: null }));
    expect(screen.getByText('Salary not listed')).toBeInTheDocument();
    expect(screen.getByText('No deadline listed')).toBeInTheDocument();
  });

  it('labels required and preferred skills with text, not only color', () => {
    renderCard(makeJob());
    const required = screen.getByRole('list', { name: 'Required skills' });
    const preferred = screen.getByRole('list', { name: 'Preferred skills' });
    expect(
      within(required)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Required: React', 'Required: TypeScript']);
    expect(within(preferred).getByRole('listitem')).toHaveTextContent('Preferred: Testing Library');
  });

  it('shows the application status and indicators when the job is tracked, bookmarked and hidden', () => {
    renderCard(makeJob({ application_status: 'Saved', is_bookmarked: true, is_hidden: true }));
    expect(screen.getByText('Status: Saved')).toBeInTheDocument();
    expect(screen.getByText('Bookmarked')).toBeInTheDocument();
    expect(screen.getByText('Hidden')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Bookmark/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Unhide' })).toBeInTheDocument();
  });

  it('calls the action handlers with the job', async () => {
    const job = makeJob();
    const { user, onToggleBookmark, onToggleHidden, onMarkApplied } = renderCard(job);
    const bookmark = screen.getByRole('button', { name: /Bookmark/ });
    expect(bookmark).toHaveAttribute('aria-pressed', 'false');
    await user.click(bookmark);
    await user.click(screen.getByRole('button', { name: 'Hide' }));
    await user.click(screen.getByRole('button', { name: 'Mark as applied' }));
    expect(onToggleBookmark).toHaveBeenCalledWith(job);
    expect(onToggleHidden).toHaveBeenCalledWith(job);
    expect(onMarkApplied).toHaveBeenCalledWith(job);
  });

  it('disables Mark as applied with the reason as its title when unavailable', () => {
    renderCard(makeJob({ application_status: 'Applied' }), {
      markApplied: { available: false, reason: 'Already marked as applied.' },
    });
    const apply = screen.getByRole('button', { name: 'Mark as applied' });
    expect(apply).toBeDisabled();
    expect(apply).toHaveAttribute('title', 'Already marked as applied.');
  });

  it('marks the card busy and shows the action as loading when an action is pending', () => {
    renderCard(makeJob(), { pendingAction: 'hide' });
    expect(screen.getByRole('article')).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('button', { name: 'Hide (loading)' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Mark as applied' })).toBeDisabled();
  });
});
