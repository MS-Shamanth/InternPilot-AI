import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { getInterviewPrep } from '../api/interview';
import { queryKeys } from '../lib/queryKeys';
import type { InterviewPrep } from '../types/api';

/** Interview prep for a job; disabled until `jobId` is a positive integer. */
export function useInterviewPrep(jobId: number): UseQueryResult<InterviewPrep> {
  return useQuery({
    queryKey: queryKeys.interview.detail(jobId),
    queryFn: ({ signal }) => getInterviewPrep(jobId, signal),
    enabled: Number.isInteger(jobId) && jobId > 0,
  });
}
