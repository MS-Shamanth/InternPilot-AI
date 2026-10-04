import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { MutationKey, UseMutationResult } from '@tanstack/react-query';
import { invalidateFor } from '../lib/queryKeys';
import type { InvalidationKind } from '../lib/queryKeys';

/** Optional per-hook callbacks; `mutate(vars, { onSuccess })` works as well. */
export interface MutationCallbacks<TData, TVariables> {
  /** Runs after the dependent queries have been invalidated and refetched. */
  onSuccess?: (data: TData, variables: TVariables) => unknown;
  onError?: (error: Error, variables: TVariables) => unknown;
}

interface InvalidatingMutationConfig<TData, TVariables> {
  mutationFn: (variables: TVariables) => Promise<TData>;
  /** Server-state change caused by this mutation; omitted for pure computations. */
  invalidates?: InvalidationKind;
  mutationKey?: MutationKey;
  callbacks?: MutationCallbacks<TData, TVariables>;
}

/**
 * `useMutation` that invalidates its `INVALIDATION_MAP` entry on success.
 *
 * Invalidation is awaited, so `isPending` stays true until dependent queries have refetched
 * (the UI shows a pending state instead of a stale value, design.md §15.2).
 */
export function useInvalidatingMutation<TData, TVariables>({
  mutationFn,
  invalidates,
  mutationKey,
  callbacks = {},
}: InvalidatingMutationConfig<TData, TVariables>): UseMutationResult<TData, Error, TVariables> {
  const queryClient = useQueryClient();
  const { onSuccess, onError } = callbacks;
  return useMutation<TData, Error, TVariables>({
    // Only the variables are forwarded; TanStack's extra context argument is not part of the API.
    mutationFn: (variables) => mutationFn(variables),
    mutationKey,
    onSuccess: async (data, variables) => {
      if (invalidates !== undefined) {
        await invalidateFor(queryClient, invalidates);
      }
      await onSuccess?.(data, variables);
    },
    onError: async (error, variables) => {
      await onError?.(error, variables);
    },
  });
}
