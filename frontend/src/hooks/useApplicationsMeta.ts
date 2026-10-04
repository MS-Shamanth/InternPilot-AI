import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { getApplicationsMeta } from '../api/applications';
import { queryKeys } from '../lib/queryKeys';
import type { ApplicationsMeta } from '../types/api';

/** Statuses and allowed transitions; fixed for the life of the backend, so never stale. */
export function useApplicationsMeta(): UseQueryResult<ApplicationsMeta> {
  return useQuery({
    queryKey: queryKeys.applications.meta(),
    queryFn: ({ signal }) => getApplicationsMeta(signal),
    staleTime: Infinity,
  });
}
