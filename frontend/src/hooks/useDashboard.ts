import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { getDashboard } from '../api/dashboard';
import { queryKeys } from '../lib/queryKeys';
import type { Dashboard } from '../types/api';

export function useDashboard(): UseQueryResult<Dashboard> {
  return useQuery({
    queryKey: queryKeys.dashboard(),
    queryFn: ({ signal }) => getDashboard(signal),
  });
}
