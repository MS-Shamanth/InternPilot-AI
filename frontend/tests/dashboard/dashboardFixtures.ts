import type { Dashboard, StatusCount, WeeklyApplicationCount } from '../../src/types/api';

const STATUSES = [
  'Saved',
  'Interested',
  'Applied',
  'Assessment',
  'Interview',
  'Rejected',
  'Offer',
  'Withdrawn',
] as const;

const WEEK_STARTS = [
  '2025-01-06',
  '2025-01-13',
  '2025-01-20',
  '2025-01-27',
  '2025-02-03',
  '2025-02-10',
  '2025-02-17',
  '2025-02-24',
] as const;

/** All eight statuses in canonical order; counts default to 0. */
export function statusBreakdown(counts: Partial<Record<StatusCount['status'], number>> = {}) {
  return STATUSES.map((status) => ({ status, count: counts[status] ?? 0 }));
}

/** Eight weeks, oldest first; `counts[i]` belongs to week `i` (missing → 0). */
export function weeklyCounts(counts: readonly number[] = []): WeeklyApplicationCount[] {
  return WEEK_STARTS.map((week_start, index) => ({ week_start, count: counts[index] ?? 0 }));
}

/** A dashboard with no data at all, as the backend returns it for a fresh user (R6.5). */
export function makeEmptyDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    total_jobs_discovered: 0,
    matching_jobs: 0,
    applications_submitted: 0,
    interviews_scheduled: 0,
    offers_received: 0,
    response_rate: 0,
    upcoming_deadlines: [],
    recent_activity: [],
    top_recommendations: [],
    status_breakdown: statusBreakdown(),
    applications_over_time: weeklyCounts(),
    score_distribution: [
      { bucket: '0-19', count: 0 },
      { bucket: '20-39', count: 0 },
      { bucket: '40-59', count: 0 },
      { bucket: '60-79', count: 0 },
      { bucket: '80-100', count: 0 },
    ],
    ...overrides,
  };
}

export function makeDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return makeEmptyDashboard({
    total_jobs_discovered: 24,
    matching_jobs: 9,
    applications_submitted: 7,
    interviews_scheduled: 2,
    offers_received: 1,
    response_rate: 42.9,
    upcoming_deadlines: [
      {
        job_id: 7,
        application_id: 3,
        title: 'Frontend Intern',
        company: 'Example Labs',
        deadline: '2025-02-24',
        days_left: 0,
        kind: 'application',
      },
      {
        job_id: 12,
        application_id: null,
        title: 'Data Analyst Intern',
        company: 'Sample Analytics',
        deadline: '2025-03-01',
        days_left: 5,
        kind: 'bookmark',
      },
    ],
    recent_activity: [
      {
        id: 31,
        type: 'status_changed',
        message: 'Moved Frontend Intern to Interview',
        job_id: 7,
        application_id: 3,
        created_at: '2025-02-23T10:15:00Z',
      },
      {
        id: 30,
        type: 'job_bookmarked',
        message: 'Bookmarked Data Analyst Intern',
        job_id: 12,
        application_id: null,
        created_at: '2025-02-22T08:00:00Z',
      },
    ],
    status_breakdown: statusBreakdown({ Saved: 3, Applied: 4, Interview: 2, Offer: 1 }),
    applications_over_time: weeklyCounts([0, 1, 0, 2, 0, 1, 3, 0]),
    top_recommendations: [
      {
        job_id: 21,
        title: 'Backend Intern',
        company: 'Example Cloud',
        location: 'Remote',
        score: 87,
      },
    ],
    score_distribution: [
      { bucket: '0-19', count: 2 },
      { bucket: '20-39', count: 5 },
      { bucket: '40-59', count: 8 },
      { bucket: '60-79', count: 6 },
      { bucket: '80-100', count: 3 },
    ],
    ...overrides,
  });
}
