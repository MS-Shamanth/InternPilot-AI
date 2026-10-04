import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '../../src/AppProviders';
import { ApiError } from '../../src/api/client';
import { getInterviewPrep } from '../../src/api/interview';
import { listJobs } from '../../src/api/jobs';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';
import InterviewPage from '../../src/pages/InterviewPage';
import type { InterviewPrep } from '../../src/types/api';
import { makeJob, makePage } from '../jobs/jobFixtures';

vi.mock('../../src/api/jobs');
vi.mock('../../src/api/interview');

const prepMock = vi.mocked(getInterviewPrep);

const PREP: InterviewPrep = {
  job_id: 1,
  provider: 'template',
  sections: [
    {
      category: 'technical',
      title: 'Technical questions',
      questions: [
        { id: 'technical-1', category: 'technical', text: 'Explain React hooks.', skill: 'React' },
      ],
    },
    {
      category: 'hr',
      title: 'HR questions',
      questions: [{ id: 'hr-1', category: 'hr', text: 'Why this company?', skill: null }],
    },
  ],
  prep_topics: [
    { topic: 'TypeScript', reason: 'Required skill missing from your profile.', priority: 'high' },
  ],
};

function renderPage(path: string) {
  render(
    <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE_FLAGS}>
      <AppProviders>
        <Routes>
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/interview/:jobId" element={<InterviewPage />} />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  );
  return { user: userEvent.setup() };
}

beforeEach(() => {
  vi.mocked(listJobs).mockResolvedValue(makePage([makeJob()]));
  prepMock.mockResolvedValue(PREP);
});

describe('InterviewPage', () => {
  it('loads prep for the picked job when a job is chosen on /interview', async () => {
    const { user } = renderPage('/interview');
    expect(screen.getByText('Choose a job to prepare for')).toBeInTheDocument();
    await user.selectOptions(await screen.findByRole('combobox', { name: /^Job/ }), '1');
    expect(await screen.findByRole('region', { name: 'Technical questions' })).toHaveTextContent(
      'Explain React hooks.',
    );
    expect(prepMock).toHaveBeenCalledWith(1, expect.any(AbortSignal));
  });

  it('shows the sections and prep topics with priority text when opened at /interview/:jobId', async () => {
    renderPage('/interview/1');
    expect(await screen.findByRole('region', { name: 'HR questions' })).toHaveTextContent(
      'Why this company?',
    );
    const topics = screen.getByRole('region', { name: 'Prep topics' });
    expect(topics).toHaveTextContent('TypeScript');
    expect(topics).toHaveTextContent('High priority');
    expect(topics).toHaveTextContent('Required skill missing from your profile.');
  });

  it('shows a not-found state when the job does not exist', async () => {
    prepMock.mockRejectedValue(new ApiError('NOT_FOUND', 'Job not found.', 404));
    renderPage('/interview/99');
    expect(await screen.findByRole('heading', { name: 'Job not found' })).toBeInTheDocument();
  });
});
