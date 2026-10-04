import type { Recommendation } from '../types/api';
import { api } from './client';

/** `GET /recommendations`; `limit` 1–20, backend default 5. */
export function listRecommendations(
  limit?: number,
  signal?: AbortSignal,
): Promise<Recommendation[]> {
  return api.get<Recommendation[]>('/recommendations', { query: { limit }, signal });
}
