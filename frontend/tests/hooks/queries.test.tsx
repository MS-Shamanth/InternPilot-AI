import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { listApplications } from '../../src/api/applications';
import { getInterviewPrep } from '../../src/api/interview';
import { getJob, listJobs } from '../../src/api/jobs';
import { listRecommendations } from '../../src/api/recommendations';
import { useApplications } from '../../src/hooks/useApplications';
import { useInterviewPrep } from '../../src/hooks/useInterviewPrep';
import { useJob } from '../../src/hooks/useJob';
import { useJobs } from '../../src/hooks/useJobs';
import { useRecommendations } from '../../src/hooks/useRecommendations';
import { queryKeys } from '../../src/lib/queryKeys';
import type { JobListParams, JobSummary, Page } from '../../src/types/api';
import { createTestQueryClient, createWrapper } from './queryTestUtils';

vi.mock('../../src/api/applications');
vi.mock('../../src/api/interview');
vi.mock('../../src/api/jobs');
vi.mock('../../src/api/recommendations');

function emptyPage(page: number): Page<JobSummary> {
  return { items: [], total: 0, page, page_size: 20, total_pages: 0 };
}

describe('useJobs', () => {
  it('passes params and the abort signal to listJobs when fetching', async () => {
    vi.mocked(listJobs).mockResolvedValue(emptyPage(1));
    const params: JobListParams = { q: 'react', work_mode: ['remote'], page: 1 };
    const { result } = renderHook(() => useJobs(params), {
      wrapper: createWrapper(createTestQueryClient()),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(listJobs).toHaveBeenCalledWith(params, expect.any(AbortSignal));
  });

  it('uses a new cache key and keeps the previous page visible when params change', async () => {
    const queryClient = createTestQueryClient();
    let resolvePageTwo: (page: Page<JobSummary>) => void = () => undefined;
    vi.mocked(listJobs).mockImplementation((params: JobListParams = {}) =>
      params.page === 2
        ? new Promise((resolve) => {
            resolvePageTwo = resolve;
          })
        : Promise.resolve(emptyPage(1)),
    );
    const { result, rerender } = renderHook((params: JobListParams) => useJobs(params), {
      initialProps: { page: 1 },
      wrapper: createWrapper(queryClient),
    });
    await waitFor(() => {
      expect(result.current.data?.page).toBe(1);
    });

    rerender({ page: 2 });

    await waitFor(() => {
      expect(listJobs).toHaveBeenLastCalledWith({ page: 2 }, expect.any(AbortSignal));
    });
    expect(result.current.isPlaceholderData).toBe(true);
    expect(result.current.data?.page).toBe(1);

    resolvePageTwo(emptyPage(2));
    await waitFor(() => {
      expect(result.current.data?.page).toBe(2);
    });
    expect(queryClient.getQueryData(queryKeys.jobs.list({ page: 1 }))).toEqual(emptyPage(1));
    expect(queryClient.getQueryData(queryKeys.jobs.list({ page: 2 }))).toEqual(emptyPage(2));
  });
});

describe('useJob', () => {
  it('does not fetch when the job id is not a positive integer', () => {
    renderHook(() => useJob(Number.NaN), { wrapper: createWrapper(createTestQueryClient()) });

    expect(getJob).not.toHaveBeenCalled();
  });
});

describe('useInterviewPrep', () => {
  it('fetches prep for the job when the id is valid', async () => {
    vi.mocked(getInterviewPrep).mockResolvedValue({
      job_id: 3,
      provider: 'template',
      sections: [],
      prep_topics: [],
    });
    const { result } = renderHook(() => useInterviewPrep(3), {
      wrapper: createWrapper(createTestQueryClient()),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(getInterviewPrep).toHaveBeenCalledWith(3, expect.any(AbortSignal));
  });
});

describe('useApplications', () => {
  it('passes the status filter to listApplications when fetching', async () => {
    vi.mocked(listApplications).mockResolvedValue([]);
    const { result } = renderHook(() => useApplications({ status: ['Applied', 'Interview'] }), {
      wrapper: createWrapper(createTestQueryClient()),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(listApplications).toHaveBeenCalledWith(
      { status: ['Applied', 'Interview'] },
      expect.any(AbortSignal),
    );
  });
});

describe('useRecommendations', () => {
  it('passes the limit to listRecommendations when fetching', async () => {
    vi.mocked(listRecommendations).mockResolvedValue([]);
    const { result } = renderHook(() => useRecommendations(3), {
      wrapper: createWrapper(createTestQueryClient()),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(listRecommendations).toHaveBeenCalledWith(3, expect.any(AbortSignal));
  });
});
