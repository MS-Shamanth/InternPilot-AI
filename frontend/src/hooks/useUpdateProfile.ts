import type { UseMutationResult } from '@tanstack/react-query';
import { updateProfile } from '../api/profile';
import type { Profile, ProfileUpdate } from '../types/api';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

/** `PUT /profile`; refreshes everything match-dependent (R1.6). */
export function useUpdateProfile(
  callbacks?: MutationCallbacks<Profile, ProfileUpdate>,
): UseMutationResult<Profile, Error, ProfileUpdate> {
  return useInvalidatingMutation({
    mutationFn: updateProfile,
    invalidates: 'profileUpdated',
    callbacks,
  });
}
