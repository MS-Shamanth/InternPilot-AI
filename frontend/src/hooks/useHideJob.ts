import type { UseMutationResult } from '@tanstack/react-query';
import { hideJob, unhideJob } from '../api/jobs';
import type { JobState } from '../types/api';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

export interface HideJobVariables {
  jobId: number;
  /** `true` hides the job (`PUT`), `false` un-hides it (`DELETE`); both idempotent. */
  hidden: boolean;
}

export function useHideJob(
  callbacks?: MutationCallbacks<JobState, HideJobVariables>,
): UseMutationResult<JobState, Error, HideJobVariables> {
  return useInvalidatingMutation({
    mutationFn: ({ jobId, hidden }: HideJobVariables) =>
      hidden ? hideJob(jobId) : unhideJob(jobId),
    invalidates: 'jobStateChanged',
    callbacks,
  });
}
