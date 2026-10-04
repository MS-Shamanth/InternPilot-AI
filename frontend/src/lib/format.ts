/**
 * Display formatting for amounts and dates. Pure: callers pass "today" explicitly.
 *
 * Output uses a fixed `en-US` locale so the English UI reads consistently. Calendar dates
 * (`YYYY-MM-DD`) are handled as UTC midnights, so day differences never shift with the
 * browser's time zone or daylight saving.
 */
import type { IsoDate, IsoDateTime, JobSummary, SalaryPeriod } from '../types/api';

const LOCALE = 'en-US';
const MS_PER_DAY = 86_400_000;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export const SALARY_NOT_LISTED = 'Salary not listed';

const PERIOD_SUFFIX: Readonly<Record<SalaryPeriod, string>> = {
  year: 'per year',
  month: 'per month',
  hour: 'per hour',
};

export type SalaryFields = Pick<
  JobSummary,
  'salary_min' | 'salary_max' | 'salary_currency' | 'salary_period'
>;

function amountFormatter(currency: string | null): (amount: number) => string {
  if (currency !== null) {
    try {
      const formatter = new Intl.NumberFormat(LOCALE, {
        style: 'currency',
        currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      });
      return (amount) => formatter.format(amount);
    } catch (error) {
      // An unknown currency code: show the code next to a plain number instead.
      if (!(error instanceof RangeError)) {
        throw error;
      }
    }
  }
  const plain = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 2 });
  const prefix = currency === null ? '' : `${currency} `;
  return (amount) => `${prefix}${plain.format(amount)}`;
}

/** "€45,000–€55,000 per year", "From $20 per hour", "Up to …", or "Salary not listed". */
export function formatSalary({
  salary_min: min,
  salary_max: max,
  salary_currency: currency,
  salary_period: period,
}: SalaryFields): string {
  if (min === null && max === null) {
    return SALARY_NOT_LISTED;
  }
  const format = amountFormatter(currency);
  let amount: string;
  if (min !== null && max !== null) {
    amount = min === max ? format(min) : `${format(min)}–${format(max)}`;
  } else if (min !== null) {
    amount = `From ${format(min)}`;
  } else {
    amount = `Up to ${format(max ?? 0)}`;
  }
  return period === null ? amount : `${amount} ${PERIOD_SUFFIX[period]}`;
}

/** UTC midnight (ms) of a valid `YYYY-MM-DD` date, else `null`. */
function utcDay(value: IsoDate): number | null {
  const match = ISO_DATE.exec(value);
  if (match === null) {
    return null;
  }
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const time = Date.UTC(year, month - 1, day);
  const parsed = new Date(time);
  const valid =
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day;
  return valid ? time : null;
}

/** The browser's local calendar date as `YYYY-MM-DD` (display only). */
export function localIsoDate(date: Date): IsoDate {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${String(date.getFullYear())}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Whole days from `from` to `to` (negative when `to` is earlier); `null` for invalid dates. */
export function daysBetween(from: IsoDate, to: IsoDate): number | null {
  const start = utcDay(from);
  const end = utcDay(to);
  return start === null || end === null ? null : Math.round((end - start) / MS_PER_DAY);
}

/** "Mar 15, 2025"; an unparseable value is returned unchanged. */
export function formatDate(value: IsoDate): string {
  const time = utcDay(value);
  if (time === null) {
    return value;
  }
  return new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium', timeZone: 'UTC' }).format(time);
}

/**
 * A timestamp in the viewer's time zone (or `timeZone`), with the zone named:
 * "Mar 15, 2025, 2:30 PM UTC". An unparseable value is returned unchanged.
 */
export function formatDateTime(value: IsoDateTime, timeZone?: string): string {
  const time = Date.parse(value);
  if (Number.isNaN(time)) {
    return value;
  }
  return new Intl.DateTimeFormat(LOCALE, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
    ...(timeZone === undefined ? {} : { timeZone }),
  }).format(time);
}

/** "12 days left", "1 day left", "Closes today", "Closed 3 days ago"; `null` if invalid. */
export function daysLeftText(deadline: IsoDate, today: IsoDate): string | null {
  const days = daysBetween(today, deadline);
  if (days === null) {
    return null;
  }
  if (days === 0) {
    return 'Closes today';
  }
  const count = Math.abs(days);
  const unit = count === 1 ? 'day' : 'days';
  return days > 0 ? `${String(count)} ${unit} left` : `Closed ${String(count)} ${unit} ago`;
}
