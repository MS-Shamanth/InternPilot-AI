import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api/client';
import { getProfile } from '../../src/api/profile';
import { useProfile } from '../../src/hooks/useProfile';
import {
  MAX_QUERY_RETRIES,
  QUERY_STALE_TIME_MS,
  createQueryClient,
  queryRetryDelay,
  shouldRetryQuery,
} from '../../src/lib/queryClient';
import { createTestQueryClient, createWrapper } from './queryTestUtils';

vi.mock('../../src/api/profile');

describe('shouldRetryQuery', () => {
  it.each([400, 401, 404, 409, 413, 422])('does not retry when the API answers %i', (status) => {
    expect(shouldRetryQuery(0, new ApiError('X', 'x', status))).toBe(false);
  });

  it.each([0, 500, 502, 503])('retries when the failure status is %i', (status) => {
    expect(shouldRetryQuery(0, new ApiError('X', 'x', status))).toBe(true);
    expect(shouldRetryQuery(MAX_QUERY_RETRIES - 1, new ApiError('X', 'x', status))).toBe(true);
  });

  it('stops retrying when the retry budget is used up', () => {
    expect(shouldRetryQuery(MAX_QUERY_RETRIES, new ApiError('X', 'x', 503))).toBe(false);
  });

  it('does not retry when the error is not an ApiError', () => {
    expect(shouldRetryQuery(0, new Error('VITE_API_BASE_URL is not configured'))).toBe(false);
  });
});

describe('createQueryClient', () => {
  it('uses the documented defaults when created', () => {
    const { queries, mutations } = createQueryClient().getDefaultOptions();

    expect(queries?.staleTime).toBe(QUERY_STALE_TIME_MS);
    expect(queries?.retry).toBe(shouldRetryQuery);
    expect(queries?.retryDelay).toBe(queryRetryDelay);
    expect(queries?.refetchOnWindowFocus).toBe(false);
    expect(mutations?.retry).toBe(false);
  });

  it('backs off exponentially with a cap when retrying', () => {
    expect([0, 1, 2, 10].map(queryRetryDelay)).toEqual([500, 1000, 2000, 5000]);
  });
});

describe('query retry policy', () => {
  it('fails after one request when the API answers 404', async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError('NOT_FOUND', 'Not found', 404));
    const { result } = renderHook(() => useProfile(), {
      wrapper: createWrapper(createTestQueryClient()),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(getProfile).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['a network error', new ApiError('NETWORK_ERROR', 'offline', 0)],
    ['a 503', new ApiError('DATABASE_UNAVAILABLE', 'down', 503)],
  ])('retries up to the budget when the request fails with %s', async (_label, error) => {
    vi.mocked(getProfile).mockRejectedValue(error);
    const { result } = renderHook(() => useProfile(), {
      wrapper: createWrapper(createTestQueryClient()),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(getProfile).toHaveBeenCalledTimes(1 + MAX_QUERY_RETRIES);
    expect(result.current.error).toBe(error);
  });
});
