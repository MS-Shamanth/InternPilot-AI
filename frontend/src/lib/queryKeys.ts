/**
 * TanStack Query keys and the mutation → invalidation map (design.md §15.2, R1.6, R6.3).
 *
 * Keys are hierarchical arrays, so invalidating a prefix (e.g. `['jobs', 'list']`) refreshes
 * every query below it (every filter/page combination). Scores, recommendations, dashboard
 * metrics and interview prep all depend on server state, so a mutation invalidates every
 * family that can show what it changed; nothing is patched optimistically.
 */
import type { QueryClient, QueryKey } from '@tanstack/react-query';
import type { ApplicationListParams, JobListParams } from '../types/api';

export const queryKeys = {
  profile: () => ['profile'] as const,
  jobs: {
    all: () => ['jobs'] as const,
    lists: () => ['jobs', 'list'] as const,
    list: (params: JobListParams) => ['jobs', 'list', params] as const,
    details: () => ['jobs', 'detail'] as const,
    detail: (jobId: number) => ['jobs', 'detail', jobId] as const,
  },
  applications: {
    all: () => ['applications'] as const,
    lists: () => ['applications', 'list'] as const,
    list: (params: ApplicationListParams) => ['applications', 'list', params] as const,
    meta: () => ['applications', 'meta'] as const,
  },
  dashboard: () => ['dashboard'] as const,
  recommendations: {
    all: () => ['recommendations'] as const,
    list: (limit: number | undefined) => ['recommendations', { limit }] as const,
  },
  interview: {
    all: () => ['interview'] as const,
    detail: (jobId: number) => ['interview', jobId] as const,
  },
  /** Mutation key of resume analysis (a `POST` compute; results are not cached as queries). */
  resume: () => ['resume'] as const,
  health: () => ['health'] as const,
};

/** Server-state changes that require refetching dependent queries. */
export type InvalidationKind =
  'profileUpdated' | 'applicationChanged' | 'jobStateChanged' | 'jobsIngested';

/**
 * Which key prefixes each kind of change makes stale.
 *
 * - Profile save: everything match-dependent (scores live in job lists/detail, recommendations,
 *   dashboard; interview prep uses the profile's skills and projects), plus the profile itself.
 * - Application create/update/delete/apply: the tracker, each job's `application_status`,
 *   recommendations (exclude non-Saved/Interested jobs) and dashboard metrics.
 *   `applications.meta` is static and is not invalidated.
 * - Bookmark/hide: job flags, recommendations (hidden excluded) and dashboard metrics.
 * - Ingestion: new or updated jobs appear in lists, detail, recommendations, dashboard, the
 *   tracker's job summaries and interview prep (which uses job title and skills).
 */
export const INVALIDATION_MAP: Readonly<Record<InvalidationKind, readonly QueryKey[]>> = {
  profileUpdated: [
    queryKeys.profile(),
    queryKeys.jobs.lists(),
    queryKeys.jobs.details(),
    queryKeys.recommendations.all(),
    queryKeys.dashboard(),
    queryKeys.interview.all(),
  ],
  applicationChanged: [
    queryKeys.applications.lists(),
    queryKeys.jobs.lists(),
    queryKeys.jobs.details(),
    queryKeys.recommendations.all(),
    queryKeys.dashboard(),
  ],
  jobStateChanged: [
    queryKeys.jobs.lists(),
    queryKeys.jobs.details(),
    queryKeys.recommendations.all(),
    queryKeys.dashboard(),
  ],
  jobsIngested: [
    queryKeys.jobs.lists(),
    queryKeys.jobs.details(),
    queryKeys.recommendations.all(),
    queryKeys.dashboard(),
    queryKeys.applications.lists(),
    queryKeys.interview.all(),
  ],
};

/** Invalidate every prefix mapped to `kind`; resolves once active queries have refetched. */
export async function invalidateFor(
  queryClient: QueryClient,
  kind: InvalidationKind,
): Promise<void> {
  await Promise.all(
    INVALIDATION_MAP[kind].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  );
}
