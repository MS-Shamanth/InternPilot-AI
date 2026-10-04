import type { HealthResponse } from '../types/api';
import { api } from './client';

const SERVICE_UNAVAILABLE = 503;

/** `GET /health`: 503 still carries the health body (degraded), so it resolves instead of throwing. */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return api.get<HealthResponse>('/health', { signal, acceptStatuses: [SERVICE_UNAVAILABLE] });
}
