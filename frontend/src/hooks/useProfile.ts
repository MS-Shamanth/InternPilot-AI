import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { getProfile } from '../api/profile';
import { queryKeys } from '../lib/queryKeys';
import type { Profile } from '../types/api';

export function useProfile(): UseQueryResult<Profile> {
  return useQuery({
    queryKey: queryKeys.profile(),
    queryFn: ({ signal }) => getProfile(signal),
  });
}
