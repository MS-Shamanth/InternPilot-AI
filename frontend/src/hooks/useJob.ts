import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { getJob } from '../api/jobs';
import { queryKeys } from '../lib/queryKeys';
import type { JobDetail } from '../types/api';

/** Job detail; disabled until `jobId` is a positive integer (e.g. parsed from the URL). */
export function useJob(jobId: number): UseQueryResult<JobDetail> {
  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId),
    queryFn: ({ signal }) => getJob(jobId, signal),
    enabled: Number.isInteger(jobId) && jobId > 0,
  });
}
