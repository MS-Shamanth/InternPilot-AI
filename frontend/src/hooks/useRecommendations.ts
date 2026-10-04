import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { listRecommendations } from '../api/recommendations';
import { queryKeys } from '../lib/queryKeys';
import type { Recommendation } from '../types/api';

/** Top recommendations; `limit` 1-20, omitted = backend default (5). */
export function useRecommendations(limit?: number): UseQueryResult<Recommendation[]> {
  return useQuery({
    queryKey: queryKeys.recommendations.list(limit),
    queryFn: ({ signal }) => listRecommendations(limit, signal),
  });
}
