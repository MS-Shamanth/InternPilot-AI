import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '../../src/AppProviders';
import { ApiError } from '../../src/api/client';
import { listJobs } from '../../src/api/jobs';
import { analyzeResume } from '../../src/api/resume';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';
import ResumePage from '../../src/pages/ResumePage';
import type { ResumeAnalysis } from '../../src/types/api';
import { makeJob, makeMatchExplanation, makePage } from '../jobs/jobFixtures';

vi.mock('../../src/api/jobs');
vi.mock('../../src/api/resume');

const analyzeMock = vi.mocked(analyzeResume);

const ANALYSIS: ResumeAnalysis = {
  job_id: 1,
  resume_source: 'profile',
  word_count: 240,
  compatibility_score: 64,
  matching_skills: [{ skill: 'React', is_required: true }],
  missing_skills: [{ skill: 'TypeScript', is_required: true, in_profile: true }],
  relevant_projects: [
    { name: 'Portfolio site', matched_skills: ['React'], mentioned_in_resume: false },
  ],
  missing_keywords: ['accessibility'],
  suggestions: [
    {
      rule: 'ADD_PROFILE_SKILL',
      message: 'Add TypeScript to your resume.',
      evidence: ['TypeScript is a required skill and is in your profile.'],
    },
  ],
  match_explanation: makeMatchExplanation(),
};

function renderPage(path = '/resume') {
  render(
    <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE_FLAGS}>
      <AppProviders>
        <Routes>
          <Route path="/resume" element={<ResumePage />} />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  );
  return { user: userEvent.setup() };
}

beforeEach(() => {
  vi.mocked(listJobs).mockResolvedValue(makePage([makeJob({ match_score: 72 })]));
  analyzeMock.mockResolvedValue(ANALYSIS);
});

describe('ResumePage', () => {
  it('analyzes the profile resume when the text is blank and shows every result section', async () => {
    const { user } = renderPage();
    const picker = await screen.findByRole('combobox', { name: /^Job/ });
    const submit = screen.getByRole('button', { name: 'Analyze resume' });
    expect(submit).toBeDisabled();
    await user.selectOptions(picker, '1');
    await user.click(submit);

    expect(analyzeMock).toHaveBeenCalledWith({ job_id: 1, resume_text: null });
    expect(await screen.findByText('COMPATIBILITY SCORE: 64/100')).toBeInTheDocument();
    expect(screen.getByText('Analyzed your profile resume (240 words).')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Matching skills' })).toHaveTextContent('React');
    expect(screen.getByRole('list', { name: 'Missing skills' })).toHaveTextContent(
      'Required · in your profile',
    );
    expect(screen.getByRole('region', { name: 'Relevant projects' })).toHaveTextContent(
      'Portfolio site',
    );
    expect(screen.getByRole('list', { name: 'Missing keywords' })).toHaveTextContent(
      'accessibility',
    );
    const suggestions = screen.getByRole('region', { name: 'Suggestions' });
    expect(suggestions).toHaveTextContent('Add TypeScript to your resume.');
    expect(within(suggestions).getByRole('list', { name: 'Evidence' })).toHaveTextContent(
      'TypeScript is a required skill and is in your profile.',
    );
  });

  it('sends pasted text for the job from ?jobId= when text is entered', async () => {
    const { user } = renderPage('/resume?jobId=1');
    await user.type(await screen.findByRole('textbox', { name: /^Resume text/ }), 'React dev');
    await user.click(screen.getByRole('button', { name: 'Analyze resume' }));
    expect(analyzeMock).toHaveBeenCalledWith({ job_id: 1, resume_text: 'React dev' });
  });

  it('shows RESUME_EMPTY inline on the resume field when there is no resume', async () => {
    analyzeMock.mockRejectedValue(
      new ApiError('RESUME_EMPTY', 'Add resume text or save one in your profile.', 422),
    );
    const { user } = renderPage('/resume?jobId=1');
    await user.click(await screen.findByRole('button', { name: 'Analyze resume' }));
    const field = screen.getByRole('textbox', { name: /^Resume text/ });
    expect(await screen.findByText('Add resume text or save one in your profile.')).toBeVisible();
    expect(field).toHaveAttribute('aria-invalid', 'true');
  });
});
