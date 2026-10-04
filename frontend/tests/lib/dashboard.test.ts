import { describe, expect, it } from 'vitest';
import tailwindConfig from '../../tailwind.config';
import { CHART_COLORS } from '../../src/lib/chartColors';
import {
  ACTIVITY_TYPE_LABELS,
  DEADLINE_KIND_LABELS,
  applicationCountText,
  dueInText,
  formatPercent,
  formatWeekStart,
  hasAnyCount,
  isDashboardEmpty,
} from '../../src/lib/dashboard';
import { makeDashboard, makeEmptyDashboard, statusBreakdown } from '../dashboard/dashboardFixtures';

describe('formatPercent', () => {
  it.each([
    [42.9, '42.9%'],
    [0, '0.0%'],
    [100, '100.0%'],
    [33.3, '33.3%'],
  ])('formats %s as %s', (value, expected) => {
    expect(formatPercent(value)).toBe(expected);
  });
});

describe('dueInText', () => {
  it.each([
    [0, 'Due today'],
    [1, 'Due tomorrow'],
    [5, 'Due in 5 days'],
    [14, 'Due in 14 days'],
    [-1, 'Overdue by 1 day'],
    [-3, 'Overdue by 3 days'],
  ])('describes %s days left as %s', (days, expected) => {
    expect(dueInText(days)).toBe(expected);
  });
});

describe('formatWeekStart', () => {
  it('formats a week start as a short month and day', () => {
    expect(formatWeekStart('2025-03-03')).toBe('Mar 3');
  });

  it('returns the value unchanged when it is not a date', () => {
    expect(formatWeekStart('soon')).toBe('soon');
  });
});

describe('applicationCountText', () => {
  it('uses the singular for one application', () => {
    expect(applicationCountText(1)).toBe('1 application');
  });

  it('uses the plural for other counts', () => {
    expect(applicationCountText(0)).toBe('0 applications');
    expect(applicationCountText(3)).toBe('3 applications');
  });
});

describe('hasAnyCount', () => {
  it('is false when every count is zero or the list is empty', () => {
    expect(hasAnyCount(statusBreakdown())).toBe(false);
    expect(hasAnyCount([])).toBe(false);
  });

  it('is true when one count is positive', () => {
    expect(hasAnyCount(statusBreakdown({ Withdrawn: 1 }))).toBe(true);
  });
});

describe('isDashboardEmpty', () => {
  it('is true when there are no jobs and no applications', () => {
    expect(isDashboardEmpty(makeEmptyDashboard())).toBe(true);
  });

  it('is false when jobs were discovered', () => {
    expect(isDashboardEmpty(makeEmptyDashboard({ total_jobs_discovered: 1 }))).toBe(false);
  });

  it('is false when an application is tracked in any status', () => {
    const dashboard = makeEmptyDashboard({ status_breakdown: statusBreakdown({ Saved: 1 }) });
    expect(isDashboardEmpty(dashboard)).toBe(false);
  });

  it('is false when applications were submitted', () => {
    expect(isDashboardEmpty(makeEmptyDashboard({ applications_submitted: 2 }))).toBe(false);
  });

  it('is false for a populated dashboard', () => {
    expect(isDashboardEmpty(makeDashboard())).toBe(false);
  });
});

describe('labels', () => {
  it('names every activity type and deadline kind', () => {
    expect(Object.values(ACTIVITY_TYPE_LABELS).every((label) => label.length > 0)).toBe(true);
    expect(DEADLINE_KIND_LABELS).toEqual({ application: 'Application', bookmark: 'Bookmark' });
  });
});

describe('CHART_COLORS', () => {
  it('mirrors the Tailwind design tokens', () => {
    const colors = tailwindConfig.theme?.extend?.colors as
      Record<string, Record<string, string>> | undefined;
    expect(CHART_COLORS).toEqual({
      primary: colors?.pilot?.['700'],
      accent: colors?.signal?.['700'],
      grid: colors?.ink?.['200'],
      axis: colors?.ink?.['600'],
    });
  });
});
