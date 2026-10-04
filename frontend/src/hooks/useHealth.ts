import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { getHealth } from '../api/health';
import { queryKeys } from '../lib/queryKeys';
import type { HealthResponse } from '../types/api';

/** Backend health; a degraded (503) backend resolves with `status: 'degraded'`. */
export function useHealth(): UseQueryResult<HealthResponse> {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: ({ signal }) => getHealth(signal),
  });
}
