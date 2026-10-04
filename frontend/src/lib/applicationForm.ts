/**
 * Application dialog values and their mapping to the API (R5.1, R5.7, design.md §8, §8.1).
 *
 * The form keeps every input as a string. `buildCreateBody` produces the `POST /applications`
 * body (blank optional fields omitted); `buildUpdatePatch` produces a `PATCH` with only the
 * fields that changed, sending `null` for a cleared nullable field. Validation stays on the
 * server; `applicationFieldErrors` only decides where its messages are shown.
 */
import { isApiError } from '../api/client';
import type {
  Application,
  ApplicationCreate,
  ApplicationStatus,
  ApplicationUpdate,
  IsoDateTime,
} from '../types/api';
import { NO_FIELD_ERRORS, fieldErrorsFromDetails } from './validationErrors';
import type { FieldErrors } from './validationErrors';

export interface ApplicationFormValues {
  /** Create only: the selected job id, `''` when none is chosen. */
  job_id: string;
  /** Create only: status moves after creation go through the Move controls. */
  status: ApplicationStatus;
  notes: string;
  applied_at: string;
  deadline: string;
  /** `datetime-local` value in the viewer's time zone, `YYYY-MM-DDTHH:mm`. */
  interview_date: string;
  recruiter_name: string;
  recruiter_email: string;
  outcome: string;
}

export type ApplicationFormField = keyof ApplicationFormValues;

/** Fields the backend lets `null` clear. */
const NULLABLE_FIELDS = [
  'applied_at',
  'deadline',
  'interview_date',
  'recruiter_name',
  'recruiter_email',
  'outcome',
] as const;
type NullableField = (typeof NULLABLE_FIELDS)[number];
type NullableValues = { [K in NullableField]: string | null };

const DUPLICATE_APPLICATION = 'DUPLICATE_APPLICATION';
const VALIDATION_STATUS = 422;
const DEFAULT_STATUS: ApplicationStatus = 'Saved';
const LOCAL_DATE_TIME = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/;

function pad(value: number): string {
  return String(value).padStart(2, '0');
}

/**
 * A `datetime-local` value (viewer's time zone) → ISO-8601 UTC, `2025-02-10T14:30:00Z`.
 * Blank → `null`. A value that is not a local date-time is returned trimmed so the server
 * reports it as a validation error instead of it being silently dropped.
 */
export function dateTimeLocalToIso(value: string): IsoDateTime | null {
  const trimmed = value.trim();
  if (trimmed === '') {
    return null;
  }
  const match = LOCAL_DATE_TIME.exec(trimmed);
  if (match === null) {
    return trimmed;
  }
  const [, year, month, day, hour, minute, second = '0'] = match;
  const local = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
  );
  if (Number.isNaN(local.getTime())) {
    return trimmed;
  }
  return local.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

/** An ISO timestamp → `datetime-local` value in the viewer's time zone; `''` for null/invalid. */
export function isoToDateTimeLocal(value: IsoDateTime | null): string {
  if (value === null) {
    return '';
  }
  const time = Date.parse(value);
  if (Number.isNaN(time)) {
    return '';
  }
  const date = new Date(time);
  return (
    `${String(date.getFullYear())}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function emptyApplicationForm(): ApplicationFormValues {
  return {
    job_id: '',
    status: DEFAULT_STATUS,
    notes: '',
    applied_at: '',
    deadline: '',
    interview_date: '',
    recruiter_name: '',
    recruiter_email: '',
    outcome: '',
  };
}

export function applicationToFormValues(application: Application): ApplicationFormValues {
  return {
    job_id: String(application.job_id),
    status: application.status,
    notes: application.notes,
    applied_at: application.applied_at ?? '',
    deadline: application.deadline ?? '',
    interview_date: isoToDateTimeLocal(application.interview_date),
    recruiter_name: application.recruiter_name ?? '',
    recruiter_email: application.recruiter_email ?? '',
    outcome: application.outcome ?? '',
  };
}

function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}

/** The API value of every nullable field (`null` when blank). */
function nullableValues(values: ApplicationFormValues): NullableValues {
  return {
    applied_at: blankToNull(values.applied_at),
    deadline: blankToNull(values.deadline),
    interview_date: dateTimeLocalToIso(values.interview_date),
    recruiter_name: blankToNull(values.recruiter_name),
    recruiter_email: blankToNull(values.recruiter_email),
    outcome: blankToNull(values.outcome),
  };
}

/** `POST /applications` body; blank optional fields are omitted (backend defaults apply). */
export function buildCreateBody(values: ApplicationFormValues): ApplicationCreate {
  const body: ApplicationCreate = { job_id: Number(values.job_id), status: values.status };
  if (values.notes !== '') {
    body.notes = values.notes;
  }
  const optional = nullableValues(values);
  for (const field of NULLABLE_FIELDS) {
    const value = optional[field];
    if (value !== null) {
      body[field] = value;
    }
  }
  return body;
}

/**
 * `PATCH /applications/{id}` with only the changed fields; a cleared nullable field is `null`.
 * The interview time is compared as the displayed local value, so an untouched timestamp with
 * seconds is never re-sent. Status is not part of the dialog (moves use the Move controls).
 */
export function buildUpdatePatch(
  original: Application,
  values: ApplicationFormValues,
): ApplicationUpdate {
  const before = applicationToFormValues(original);
  const next = nullableValues(values);
  const patch: ApplicationUpdate = {};
  for (const field of NULLABLE_FIELDS) {
    const changed =
      field === 'interview_date'
        ? values.interview_date.trim() !== before.interview_date
        : next[field] !== original[field];
    if (changed) {
      patch[field] = next[field];
    }
  }
  if (values.notes !== original.notes) {
    patch.notes = values.notes;
  }
  return patch;
}

export function isEmptyPatch(patch: ApplicationUpdate): boolean {
  return Object.keys(patch).length === 0;
}

/**
 * Inline errors for a failed save: 422 messages per field, and the envelope message on
 * `job_id` for 409 `DUPLICATE_APPLICATION`. Other failures are shown as toasts only.
 */
export function applicationFieldErrors(error: unknown): FieldErrors {
  if (!isApiError(error)) {
    return NO_FIELD_ERRORS;
  }
  if (error.code === DUPLICATE_APPLICATION) {
    return { job_id: error.message };
  }
  return error.status === VALIDATION_STATUS
    ? fieldErrorsFromDetails(error.details)
    : NO_FIELD_ERRORS;
}
