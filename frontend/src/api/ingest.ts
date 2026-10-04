import type { IngestRequest, IngestResult } from '../types/api';
import { api } from './client';

/** `POST /jobs/ingest`; 422 invalid request, 413 too large, 502 source down with no fallback. */
export function ingestJobs(request: IngestRequest): Promise<IngestResult> {
  return api.post<IngestResult>('/jobs/ingest', request);
}
