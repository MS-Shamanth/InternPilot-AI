import { describe, expect, it } from 'vitest';
import {
  SALARY_NOT_LISTED,
  daysBetween,
  daysLeftText,
  formatDate,
  formatDateTime,
  formatSalary,
  localIsoDate,
} from '../../src/lib/format';
import type { SalaryFields } from '../../src/lib/format';

function salary(fields: Partial<SalaryFields>): SalaryFields {
  return {
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    salary_period: null,
    ...fields,
  };
}

describe('formatSalary', () => {
  it('formats a range with currency and period', () => {
    expect(
      formatSalary(
        salary({
          salary_min: 45000,
          salary_max: 55000,
          salary_currency: 'EUR',
          salary_period: 'year',
        }),
      ),
    ).toBe('€45,000–€55,000 per year');
  });

  it('formats open-ended and single amounts', () => {
    expect(
      formatSalary(salary({ salary_min: 20, salary_currency: 'USD', salary_period: 'hour' })),
    ).toBe('From $20 per hour');
    expect(formatSalary(salary({ salary_max: 1500, salary_currency: 'USD' }))).toBe('Up to $1,500');
    expect(
      formatSalary(
        salary({
          salary_min: 1200,
          salary_max: 1200,
          salary_currency: 'GBP',
          salary_period: 'month',
        }),
      ),
    ).toBe('£1,200 per month');
  });

  it('falls back to a plain number for a missing or unknown currency', () => {
    expect(formatSalary(salary({ salary_min: 3000, salary_period: 'month' }))).toBe(
      'From 3,000 per month',
    );
    expect(formatSalary(salary({ salary_min: 3000, salary_currency: 'EURO' }))).toBe(
      'From EURO 3,000',
    );
  });

  it('says the salary is not listed when there are no amounts', () => {
    expect(formatSalary(salary({ salary_currency: 'EUR' }))).toBe(SALARY_NOT_LISTED);
  });
});

describe('dates', () => {
  it('counts calendar days between ISO dates, across month and year ends', () => {
    expect(daysBetween('2025-01-30', '2025-02-02')).toBe(3);
    expect(daysBetween('2024-12-31', '2025-01-01')).toBe(1);
    expect(daysBetween('2025-03-10', '2025-03-01')).toBe(-9);
    expect(daysBetween('2025-02-30', '2025-03-01')).toBeNull();
    expect(daysBetween('soon', '2025-03-01')).toBeNull();
  });

  it('describes the days left until a deadline', () => {
    expect(daysLeftText('2025-01-27', '2025-01-15')).toBe('12 days left');
    expect(daysLeftText('2025-01-16', '2025-01-15')).toBe('1 day left');
    expect(daysLeftText('2025-01-15', '2025-01-15')).toBe('Closes today');
    expect(daysLeftText('2025-01-14', '2025-01-15')).toBe('Closed 1 day ago');
    expect(daysLeftText('2025-01-12', '2025-01-15')).toBe('Closed 3 days ago');
    expect(daysLeftText('later', '2025-01-15')).toBeNull();
  });

  it('formats a calendar date without a time zone shift', () => {
    expect(formatDate('2025-03-01')).toBe('Mar 1, 2025');
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });

  it('formats a timestamp with its time zone named', () => {
    expect(formatDateTime('2025-02-10T14:30:00Z', 'UTC')).toBe('Feb 10, 2025, 2:30 PM UTC');
    expect(formatDateTime('2025-02-10T14:30:00Z', 'America/New_York')).toBe(
      'Feb 10, 2025, 9:30 AM EST',
    );
    expect(formatDateTime('whenever')).toBe('whenever');
  });

  it('reads the local calendar date of a Date', () => {
    expect(localIsoDate(new Date(2025, 0, 5, 23, 30))).toBe('2025-01-05');
  });
});
