import type { UseMutationResult } from '@tanstack/react-query';
import { deleteApplication } from '../api/applications';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

/** `DELETE /applications/{id}`; variables are the application id. */
export function useDeleteApplication(
  callbacks?: MutationCallbacks<undefined, number>,
): UseMutationResult<undefined, Error, number> {
  return useInvalidatingMutation({
    mutationFn: deleteApplication,
    invalidates: 'applicationChanged',
    callbacks,
  });
}
