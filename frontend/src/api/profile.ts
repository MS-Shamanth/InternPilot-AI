import type { Profile, ProfileUpdate } from '../types/api';
import { api } from './client';

/** `GET /profile`. */
export function getProfile(signal?: AbortSignal): Promise<Profile> {
  return api.get<Profile>('/profile', { signal });
}

/** `PUT /profile` (full replace); 409 `EMAIL_TAKEN`, 422 on invalid fields. */
export function updateProfile(profile: ProfileUpdate): Promise<Profile> {
  return api.put<Profile>('/profile', profile);
}
