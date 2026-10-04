import type { UseMutationResult } from '@tanstack/react-query';
import { createApplication } from '../api/applications';
import type { Application, ApplicationCreate } from '../types/api';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

export function useCreateApplication(
  callbacks?: MutationCallbacks<Application, ApplicationCreate>,
): UseMutationResult<Application, Error, ApplicationCreate> {
  return useInvalidatingMutation({
    mutationFn: createApplication,
    invalidates: 'applicationChanged',
    callbacks,
  });
}
