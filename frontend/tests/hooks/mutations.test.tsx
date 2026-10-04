import type { QueryClient } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';
import {
  createApplication,
  deleteApplication,
  updateApplication,
} from '../../src/api/applications';
import { ApiError } from '../../src/api/client';
import { ingestJobs } from '../../src/api/ingest';
import { applyToJob, bookmarkJob, hideJob, unbookmarkJob, unhideJob } from '../../src/api/jobs';
import { updateProfile } from '../../src/api/profile';
import { analyzeResume } from '../../src/api/resume';
import { useAnalyzeResume } from '../../src/hooks/useAnalyzeResume';
import { useApplyToJob } from '../../src/hooks/useApplyToJob';
import { useBookmarkJob } from '../../src/hooks/useBookmarkJob';
import { useCreateApplication } from '../../src/hooks/useCreateApplication';
import { useDeleteApplication } from '../../src/hooks/useDeleteApplication';
import { useHideJob } from '../../src/hooks/useHideJob';
import { useIngestJobs } from '../../src/hooks/useIngestJobs';
import { useUpdateApplication } from '../../src/hooks/useUpdateApplication';
import { useUpdateProfile } from '../../src/hooks/useUpdateProfile';
import { INVALIDATION_MAP } from '../../src/lib/queryKeys';
import type {
  Application,
  IngestResult,
  JobState,
  MatchExplanation,
  Profile,
  ProfileUpdate,
  ResumeAnalysis,
} from '../../src/types/api';
import { createTestQueryClient, createWrapper } from './queryTestUtils';

vi.mock('../../src/api/applications');
vi.mock('../../src/api/ingest');
vi.mock('../../src/api/jobs');
vi.mock('../../src/api/profile');
vi.mock('../../src/api/resume');

const TIMESTAMP = '2025-01-15T09:30:00Z';

const APPLICATION: Application = {
  id: 11,
  job_id: 4,
  status: 'Applied',
  applied_at: '2025-01-15',
  deadline: null,
  interview_date: null,
  recruiter_name: null,
  recruiter_email: null,
  notes: '',
  outcome: null,
  created_at: TIMESTAMP,
  updated_at: TIMESTAMP,
  job: {
    id: 4,
    title: 'Frontend Intern',
    company: 'Example Co',
    location: 'Remote',
    deadline: null,
  },
};

const PROFILE_UPDATE: ProfileUpdate = {
  name: 'Demo Student',
  email: 'demo@internpilot.dev',
  location: null,
  target_roles: [],
  preferred_locations: [],
  preferred_work_modes: [],
  experience_level: null,
  education_level: null,
  education: [],
  technical_skills: ['React'],
  soft_skills: [],
  projects: [],
  certifications: [],
  resume_text: '',
  github_url: null,
  portfolio_url: null,
  linkedin_url: null,
};

const PROFILE: Profile = { ...PROFILE_UPDATE, id: 1, created_at: TIMESTAMP, updated_at: TIMESTAMP };

const INGEST_RESULT: IngestResult = {
  requested_source: 'fixture',
  source: 'fixture',
  fallback_used: false,
  fetched: 1,
  created: 1,
  updated: 0,
  duplicates: 0,
  rejected: 0,
  errors: [],
};

const EXPLANATION: MatchExplanation = {
  job_id: 4,
  score: 50,
  algorithm_version: '1',
  factors: [],
  matched_required_skills: [],
  missing_required_skills: [],
  matched_preferred_skills: [],
  missing_preferred_skills: [],
  positive_reasons: [],
  negative_reasons: [],
};

const ANALYSIS: ResumeAnalysis = {
  job_id: 4,
  resume_source: 'request',
  word_count: 3,
  compatibility_score: 50,
  matching_skills: [],
  missing_skills: [],
  relevant_projects: [],
  missing_keywords: [],
  suggestions: [],
  match_explanation: EXPLANATION,
};

function jobState(overrides: Partial<JobState> = {}): JobState {
  return { job_id: 4, is_bookmarked: false, is_hidden: false, ...overrides };
}

let queryClient: QueryClient;
let invalidateSpy: MockInstance<QueryClient['invalidateQueries']>;

beforeEach(() => {
  queryClient = createTestQueryClient();
  invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
});

function invalidatedKeys(): unknown[] {
  return invalidateSpy.mock.calls.map(([filters]) => filters?.queryKey);
}

function render<T>(hook: () => T): { current: T } {
  return renderHook(hook, { wrapper: createWrapper(queryClient) }).result;
}

describe('mutation hooks', () => {
  it('updates the application, invalidates its keys, then calls onSuccess when the PATCH succeeds', async () => {
    vi.mocked(updateApplication).mockResolvedValue(APPLICATION);
    const onSuccess = vi.fn(() => {
      // Caller callbacks run after invalidation, so a toast never precedes fresh data.
      expect(invalidatedKeys()).toEqual(INVALIDATION_MAP.applicationChanged);
    });
    const result = render(() => useUpdateApplication({ onSuccess }));

    await act(() =>
      result.current.mutateAsync({ applicationId: 11, changes: { status: 'Interview' } }),
    );

    expect(updateApplication).toHaveBeenCalledWith(11, { status: 'Interview' });
    expect(onSuccess).toHaveBeenCalledWith(APPLICATION, {
      applicationId: 11,
      changes: { status: 'Interview' },
    });
  });

  it('invalidates the application keys when an application is created', async () => {
    vi.mocked(createApplication).mockResolvedValue(APPLICATION);
    const result = render(() => useCreateApplication());

    await act(() => result.current.mutateAsync({ job_id: 4 }));

    expect(createApplication).toHaveBeenCalledWith({ job_id: 4 });
    expect(invalidatedKeys()).toEqual(INVALIDATION_MAP.applicationChanged);
  });

  it('invalidates the application keys when an application is deleted', async () => {
    vi.mocked(deleteApplication).mockResolvedValue(undefined);
    const result = render(() => useDeleteApplication());

    await act(() => result.current.mutateAsync(11));

    expect(deleteApplication).toHaveBeenCalledWith(11);
    expect(invalidatedKeys()).toEqual(INVALIDATION_MAP.applicationChanged);
  });

  it('invalidates the application keys when a job is marked as applied', async () => {
    vi.mocked(applyToJob).mockResolvedValue(APPLICATION);
    const result = render(() => useApplyToJob());

    await act(() => result.current.mutateAsync(4));

    expect(applyToJob).toHaveBeenCalledWith(4);
    expect(invalidatedKeys()).toEqual(INVALIDATION_MAP.applicationChanged);
  });

  it('invalidates everything match-dependent when the profile is saved', async () => {
    vi.mocked(updateProfile).mockResolvedValue(PROFILE);
    const result = render(() => useUpdateProfile());

    await act(() => result.current.mutateAsync(PROFILE_UPDATE));

    expect(updateProfile).toHaveBeenCalledWith(PROFILE_UPDATE);
    expect(invalidatedKeys()).toEqual(INVALIDATION_MAP.profileUpdated);
  });

  it('invalidates job data when jobs are ingested', async () => {
    vi.mocked(ingestJobs).mockResolvedValue(INGEST_RESULT);
    const result = render(() => useIngestJobs());

    await act(() => result.current.mutateAsync({ source: 'fixture' }));

    expect(ingestJobs).toHaveBeenCalledWith({ source: 'fixture' });
    expect(invalidatedKeys()).toEqual(INVALIDATION_MAP.jobsIngested);
  });

  it('invalidates nothing when a resume is analyzed', async () => {
    vi.mocked(analyzeResume).mockResolvedValue(ANALYSIS);
    const result = render(() => useAnalyzeResume());

    await act(() => result.current.mutateAsync({ job_id: 4, resume_text: 'React and TypeScript' }));

    await waitFor(() => {
      expect(result.current.data).toEqual(ANALYSIS);
    });
    expect(analyzeResume).toHaveBeenCalledWith({ job_id: 4, resume_text: 'React and TypeScript' });
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it('calls onError and invalidates nothing when the mutation fails', async () => {
    const error = new ApiError('INVALID_STATUS_TRANSITION', 'Not allowed', 409, {
      allowed: ['Withdrawn'],
    });
    vi.mocked(updateApplication).mockRejectedValue(error);
    const onError = vi.fn();
    const result = render(() => useUpdateApplication({ onError }));

    act(() => {
      result.current.mutate({ applicationId: 11, changes: { status: 'Offer' } });
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(updateApplication).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(error, {
      applicationId: 11,
      changes: { status: 'Offer' },
    });
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});

describe('job state toggles', () => {
  it.each([
    [true, bookmarkJob, unbookmarkJob],
    [false, unbookmarkJob, bookmarkJob],
  ])('calls the matching endpoint when bookmarked is %s', async (bookmarked, called, notCalled) => {
    vi.mocked(called).mockResolvedValue(jobState({ is_bookmarked: bookmarked }));
    const result = render(() => useBookmarkJob());

    await act(() => result.current.mutateAsync({ jobId: 4, bookmarked }));

    expect(called).toHaveBeenCalledWith(4);
    expect(notCalled).not.toHaveBeenCalled();
    expect(invalidatedKeys()).toEqual(INVALIDATION_MAP.jobStateChanged);
  });

  it.each([
    [true, hideJob, unhideJob],
    [false, unhideJob, hideJob],
  ])('calls the matching endpoint when hidden is %s', async (hidden, called, notCalled) => {
    vi.mocked(called).mockResolvedValue(jobState({ is_hidden: hidden }));
    const result = render(() => useHideJob());

    await act(() => result.current.mutateAsync({ jobId: 4, hidden }));

    expect(called).toHaveBeenCalledWith(4);
    expect(notCalled).not.toHaveBeenCalled();
    expect(invalidatedKeys()).toEqual(INVALIDATION_MAP.jobStateChanged);
  });
});
