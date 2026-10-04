import type {
  Application,
  JobDetail,
  JobListParams,
  JobState,
  JobSummary,
  MatchExplanation,
  Page,
} from '../types/api';
import { api } from './client';

const SKILLS_SEPARATOR = ',';

/** `GET /jobs`: multi-valued filters are repeated parameters, `skills` is comma-separated. */
export function listJobs(
  params: JobListParams = {},
  signal?: AbortSignal,
): Promise<Page<JobSummary>> {
  const { skills, ...rest } = params;
  const query = {
    ...rest,
    skills: skills && skills.length > 0 ? skills.join(SKILLS_SEPARATOR) : undefined,
  };
  return api.get<Page<JobSummary>>('/jobs', { query, signal });
}

/** `GET /jobs/{id}`. */
export function getJob(jobId: number, signal?: AbortSignal): Promise<JobDetail> {
  return api.get<JobDetail>(`/jobs/${String(jobId)}`, { signal });
}

/** `POST /jobs/{id}/match`: recompute the explanation for the current profile. */
export function matchJob(jobId: number): Promise<MatchExplanation> {
  return api.post<MatchExplanation>(`/jobs/${String(jobId)}/match`);
}

/** `PUT /jobs/{id}/bookmark`. */
export function bookmarkJob(jobId: number): Promise<JobState> {
  return api.put<JobState>(`/jobs/${String(jobId)}/bookmark`);
}

/** `DELETE /jobs/{id}/bookmark`. */
export function unbookmarkJob(jobId: number): Promise<JobState> {
  return api.delete<JobState>(`/jobs/${String(jobId)}/bookmark`);
}

/** `PUT /jobs/{id}/hide`. */
export function hideJob(jobId: number): Promise<JobState> {
  return api.put<JobState>(`/jobs/${String(jobId)}/hide`);
}

/** `DELETE /jobs/{id}/hide`. */
export function unhideJob(jobId: number): Promise<JobState> {
  return api.delete<JobState>(`/jobs/${String(jobId)}/hide`);
}

/** `POST /jobs/{id}/apply`: creates or moves the application to Applied; 409 from other statuses. */
export function applyToJob(jobId: number): Promise<Application> {
  return api.post<Application>(`/jobs/${String(jobId)}/apply`);
}
