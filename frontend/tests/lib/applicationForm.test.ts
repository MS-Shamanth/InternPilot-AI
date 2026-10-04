import { describe, expect, it } from 'vitest';
import { ApiError } from '../../src/api/client';
import {
  applicationFieldErrors,
  applicationToFormValues,
  buildCreateBody,
  buildUpdatePatch,
  dateTimeLocalToIso,
  emptyApplicationForm,
  isEmptyPatch,
  isoToDateTimeLocal,
} from '../../src/lib/applicationForm';
import { makeTrackedApplication } from '../applications/applicationFixtures';

/** Local 2025-02-10 14:30 in whatever zone the tests run in, as the API's UTC string. */
const LOCAL_INTERVIEW_ISO = new Date(2025, 1, 10, 14, 30).toISOString().replace('.000Z', 'Z');

describe('dateTimeLocalToIso', () => {
  it('returns null when blank', () => {
    expect(dateTimeLocalToIso('  ')).toBeNull();
  });

  it('converts a local date-time to ISO UTC without milliseconds', () => {
    expect(dateTimeLocalToIso('2025-02-10T14:30')).toBe(LOCAL_INTERVIEW_ISO);
    expect(LOCAL_INTERVIEW_ISO).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00Z$/);
  });

  it('passes an unparseable value through for the server to reject', () => {
    expect(dateTimeLocalToIso('next tuesday')).toBe('next tuesday');
  });
});

describe('isoToDateTimeLocal', () => {
  it('returns an empty string for null or invalid timestamps', () => {
    expect(isoToDateTimeLocal(null)).toBe('');
    expect(isoToDateTimeLocal('not a date')).toBe('');
  });

  it('round-trips with dateTimeLocalToIso', () => {
    expect(isoToDateTimeLocal(LOCAL_INTERVIEW_ISO)).toBe('2025-02-10T14:30');
  });
});

describe('buildCreateBody', () => {
  it('sends only the job and status when nothing else is filled', () => {
    expect(buildCreateBody({ ...emptyApplicationForm(), job_id: '3' })).toEqual({
      job_id: 3,
      status: 'Saved',
    });
  });

  it('includes filled fields, trimmed, with the interview time in UTC', () => {
    const body = buildCreateBody({
      ...emptyApplicationForm(),
      job_id: '4',
      status: 'Applied',
      notes: 'Referred by a friend',
      applied_at: '2025-01-20',
      deadline: '2025-03-01',
      interview_date: '2025-02-10T14:30',
      recruiter_name: '  Alex Recruiter ',
      recruiter_email: 'recruiter@example.com',
      outcome: ' ',
    });
    expect(body).toEqual({
      job_id: 4,
      status: 'Applied',
      notes: 'Referred by a friend',
      applied_at: '2025-01-20',
      deadline: '2025-03-01',
      interview_date: LOCAL_INTERVIEW_ISO,
      recruiter_name: 'Alex Recruiter',
      recruiter_email: 'recruiter@example.com',
    });
  });
});

describe('buildUpdatePatch', () => {
  const original = makeTrackedApplication({
    notes: 'Old notes',
    recruiter_name: 'Alex Recruiter',
    deadline: '2025-03-01',
    interview_date: '2025-02-10T14:30:45Z',
  });

  it('is empty when nothing changed, even for an interview time with seconds', () => {
    const patch = buildUpdatePatch(original, applicationToFormValues(original));
    expect(patch).toEqual({});
    expect(isEmptyPatch(patch)).toBe(true);
  });

  it('sends only changed fields and null for cleared ones', () => {
    const values = {
      ...applicationToFormValues(original),
      notes: 'New notes',
      recruiter_name: '',
      deadline: '',
      outcome: 'Offer call booked',
    };
    expect(buildUpdatePatch(original, values)).toEqual({
      notes: 'New notes',
      recruiter_name: null,
      deadline: null,
      outcome: 'Offer call booked',
    });
  });

  it('sends a changed or cleared interview time', () => {
    const changed = { ...applicationToFormValues(original), interview_date: '2025-02-10T14:30' };
    const base = { ...original, interview_date: null };
    expect(buildUpdatePatch(base, changed)).toEqual({ interview_date: LOCAL_INTERVIEW_ISO });
    const cleared = { ...applicationToFormValues(original), interview_date: '' };
    expect(buildUpdatePatch(original, cleared)).toEqual({ interview_date: null });
  });

  it('ignores whitespace-only edits to trimmed text fields', () => {
    const values = { ...applicationToFormValues(original), recruiter_name: ' Alex Recruiter ' };
    expect(isEmptyPatch(buildUpdatePatch(original, values))).toBe(true);
  });
});

describe('applicationFieldErrors', () => {
  it('puts a duplicate application message on the job field', () => {
    const error = new ApiError('DUPLICATE_APPLICATION', 'Already tracked.', 409, null);
    expect(applicationFieldErrors(error)).toEqual({ job_id: 'Already tracked.' });
  });

  it('maps 422 details to field paths', () => {
    const error = new ApiError('VALIDATION_ERROR', 'Invalid request.', 422, [
      { loc: ['body', 'recruiter_email'], msg: 'value is not a valid email address', type: 'x' },
    ]);
    expect(applicationFieldErrors(error)).toEqual({
      recruiter_email: 'value is not a valid email address',
    });
  });

  it('returns no field errors for other failures', () => {
    expect(applicationFieldErrors(new ApiError('INTERNAL_ERROR', 'Oops', 500, null))).toEqual({});
    expect(applicationFieldErrors(new Error('offline'))).toEqual({});
  });
});
