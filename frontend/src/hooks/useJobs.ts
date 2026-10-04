import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { listJobs } from '../api/jobs';
import { queryKeys } from '../lib/queryKeys';
import type { JobListParams, JobSummary, Page } from '../types/api';

/** One page of jobs; the previous page stays visible while the next one loads. */
export function useJobs(params: JobListParams = {}): UseQueryResult<Page<JobSummary>> {
  return useQuery({
    queryKey: queryKeys.jobs.list(params),
    queryFn: ({ signal }) => listJobs(params, signal),
    placeholderData: keepPreviousData,
  });
}
