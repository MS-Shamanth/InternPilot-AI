import type { InterviewPrep } from '../types/api';
import { api } from './client';

/** `GET /interview/{job_id}`. */
export function getInterviewPrep(jobId: number, signal?: AbortSignal): Promise<InterviewPrep> {
  return api.get<InterviewPrep>(`/interview/${String(jobId)}`, { signal });
}
