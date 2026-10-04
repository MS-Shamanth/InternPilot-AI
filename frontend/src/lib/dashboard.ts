/**
 * Presentation helpers for the dashboard. Every number comes from `GET /api/dashboard`
 * (DashboardService); nothing here computes a metric, it only formats backend values.
 */
import type { ActivityType, Dashboard, DeadlineKind, IsoDate } from '../types/api';

const LOCALE = 'en-US';
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export const ACTIVITY_TYPE_LABELS: Readonly<Record<ActivityType, string>> = {
  application_created: 'Application added',
  status_changed: 'Status changed',
  application_updated: 'Application updated',
  application_deleted: 'Application deleted',
  job_bookmarked: 'Bookmarked',
  job_hidden: 'Hidden',
  profile_updated: 'Profile updated',
  jobs_ingested: 'Jobs imported',
};

export const DEADLINE_KIND_LABELS: Readonly<Record<DeadlineKind, string>> = {
  application: 'Application',
  bookmark: 'Bookmark',
};

/** The backend's percentage (already rounded to 1 decimal) as text: `42.9` → `"42.9%"`. */
export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

/** The backend's `days_left`: "Due today", "Due tomorrow", "Due in 5 days" ("Overdue …" if < 0). */
export function dueInText(daysLeft: number): string {
  if (daysLeft === 0) {
    return 'Due today';
  }
  if (daysLeft === 1) {
    return 'Due tomorrow';
  }
  const count = Math.abs(daysLeft);
  const unit = count === 1 ? 'day' : 'days';
  return daysLeft > 0 ? `Due in ${String(count)} ${unit}` : `Overdue by ${String(count)} ${unit}`;
}

/** Short axis label for a week's Monday: `2025-03-03` → `"Mar 3"`; invalid input is unchanged. */
export function formatWeekStart(value: IsoDate): string {
  const match = ISO_DATE.exec(value);
  if (match === null) {
    return value;
  }
  const time = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return new Intl.DateTimeFormat(LOCALE, {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(time);
}

/** "1 application" / "3 applications". */
export function applicationCountText(count: number): string {
  return `${String(count)} ${count === 1 ? 'application' : 'applications'}`;
}

/** True when any of the backend's counts is non-zero (decides between a chart and its empty state). */
export function hasAnyCount(items: readonly { count: number }[]): boolean {
  return items.some((item) => item.count > 0);
}

/**
 * The whole dashboard has nothing to show yet: no jobs discovered, no applications submitted and
 * no tracked applications in any status. Based only on backend fields.
 */
export function isDashboardEmpty(dashboard: Dashboard): boolean {
  return (
    dashboard.total_jobs_discovered === 0 &&
    dashboard.applications_submitted === 0 &&
    !hasAnyCount(dashboard.status_breakdown)
  );
}
