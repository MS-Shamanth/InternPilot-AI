/**
 * The app's `QueryClient` defaults (design.md §15.2).
 *
 * - Queries retry only failures that may be transient: network errors (`status` 0) and 5xx.
 *   4xx responses (validation, not found, conflicts, unknown demo user) are final.
 * - Mutations never retry: `POST`s are not idempotent and the server owns transitions.
 * - Data is fresh for 30 s and is not refetched on window focus; in-app changes refresh
 *   through the invalidation map (`queryKeys.ts`), and the single demo user has no other
 *   writers apart from CLI ingestion.
 */
import { QueryClient } from '@tanstack/react-query';
import { isApiError } from '../api/client';

export const QUERY_STALE_TIME_MS = 30_000;
export const MAX_QUERY_RETRIES = 2;
const RETRY_BASE_DELAY_MS = 500;
const RETRY_MAX_DELAY_MS = 5_000;

/** `true` when a failed query should be tried again (`failureCount` failures so far). */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_QUERY_RETRIES || !isApiError(error)) {
    return false;
  }
  return error.status === 0 || error.status >= 500;
}

/** Exponential backoff: 500 ms, 1 s, 2 s … capped at 5 s. */
export function queryRetryDelay(failureCount: number): number {
  return Math.min(RETRY_BASE_DELAY_MS * 2 ** failureCount, RETRY_MAX_DELAY_MS);
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: QUERY_STALE_TIME_MS,
        retry: shouldRetryQuery,
        retryDelay: queryRetryDelay,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}
