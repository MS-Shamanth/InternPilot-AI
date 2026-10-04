import type { UseMutationResult } from '@tanstack/react-query';
import { applyToJob } from '../api/jobs';
import type { Application } from '../types/api';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

/** `POST /jobs/{id}/apply` (mark as applied); variables are the job id. */
export function useApplyToJob(
  callbacks?: MutationCallbacks<Application, number>,
): UseMutationResult<Application, Error, number> {
  return useInvalidatingMutation({
    mutationFn: applyToJob,
    invalidates: 'applicationChanged',
    callbacks,
  });
}
