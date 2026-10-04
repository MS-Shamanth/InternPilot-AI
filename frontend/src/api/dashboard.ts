import type { Dashboard } from '../types/api';
import { api } from './client';

/** `GET /dashboard`: metrics computed fresh per request. */
export function getDashboard(signal?: AbortSignal): Promise<Dashboard> {
  return api.get<Dashboard>('/dashboard', { signal });
}
