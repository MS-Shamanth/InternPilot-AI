import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { listApplications } from '../api/applications';
import { queryKeys } from '../lib/queryKeys';
import type { Application, ApplicationListParams } from '../types/api';

export function useApplications(params: ApplicationListParams = {}): UseQueryResult<Application[]> {
  return useQuery({
    queryKey: queryKeys.applications.list(params),
    queryFn: ({ signal }) => listApplications(params, signal),
  });
}
