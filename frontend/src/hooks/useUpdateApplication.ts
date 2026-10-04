import type { UseMutationResult } from '@tanstack/react-query';
import { updateApplication } from '../api/applications';
import type { Application, ApplicationUpdate } from '../types/api';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

export interface UpdateApplicationVariables {
  applicationId: number;
  changes: ApplicationUpdate;
}

/** `PATCH /applications/{id}`: status moves (no optimistic update) and field edits. */
export function useUpdateApplication(
  callbacks?: MutationCallbacks<Application, UpdateApplicationVariables>,
): UseMutationResult<Application, Error, UpdateApplicationVariables> {
  return useInvalidatingMutation({
    mutationFn: ({ applicationId, changes }: UpdateApplicationVariables) =>
      updateApplication(applicationId, changes),
    invalidates: 'applicationChanged',
    callbacks,
  });
}
