import type {
  Application,
  ApplicationCreate,
  ApplicationListParams,
  ApplicationsMeta,
  ApplicationUpdate,
} from '../types/api';
import { api } from './client';

/** `GET /applications`: the user's full set (max 500); `status` filters are repeated. */
export function listApplications(
  params: ApplicationListParams = {},
  signal?: AbortSignal,
): Promise<Application[]> {
  return api.get<Application[]>('/applications', { query: { status: params.status }, signal });
}

/** `GET /applications/meta`: statuses and allowed transitions. */
export function getApplicationsMeta(signal?: AbortSignal): Promise<ApplicationsMeta> {
  return api.get<ApplicationsMeta>('/applications/meta', { signal });
}

/** `POST /applications`; 409 `DUPLICATE_APPLICATION` when the job is already tracked. */
export function createApplication(application: ApplicationCreate): Promise<Application> {
  return api.post<Application>('/applications', application);
}

/** `PATCH /applications/{id}`; 409 `INVALID_STATUS_TRANSITION` with `details.allowed`. */
export function updateApplication(
  applicationId: number,
  changes: ApplicationUpdate,
): Promise<Application> {
  return api.patch<Application>(`/applications/${String(applicationId)}`, changes);
}

/** `DELETE /applications/{id}` (204). */
export function deleteApplication(applicationId: number): Promise<undefined> {
  return api.delete<undefined>(`/applications/${String(applicationId)}`);
}
