import { describe, expect, it } from 'vitest';
import { ApiError } from '../../src/api/client';
import {
  clearFieldErrors,
  fieldDomId,
  fieldErrorsFromDetails,
  fieldErrorsFromError,
  locToFieldPath,
  parentFieldPath,
} from '../../src/lib/validationErrors';

describe('locToFieldPath', () => {
  it('drops the leading body segment for a top-level field', () => {
    expect(locToFieldPath(['body', 'email'])).toBe('email');
  });

  it('maps nested list items to bracketed indexes when loc points into a list', () => {
    expect(locToFieldPath(['body', 'projects', 1, 'url'])).toBe('projects[1].url');
    expect(locToFieldPath(['body', 'technical_skills', 3])).toBe('technical_skills[3]');
    expect(locToFieldPath(['body', 'projects', 0, 'technologies', 2])).toBe(
      'projects[0].technologies[2]',
    );
  });

  it('skips non-identifier validator tags when Pydantic adds them', () => {
    expect(locToFieldPath(['body', 'github_url', 'function-after[check(), url]'])).toBe(
      'github_url',
    );
  });

  it('returns the empty path when the error is about the whole body', () => {
    expect(locToFieldPath(['body'])).toBe('');
  });
});

describe('fieldErrorsFromDetails', () => {
  it('groups messages by path and strips the Pydantic value-error prefix', () => {
    const errors = fieldErrorsFromDetails([
      {
        loc: ['body', 'education', 0],
        msg: 'Value error, start_year must not be after end_year',
        type: 'value_error',
      },
      { loc: ['body', 'name'], msg: 'Field required', type: 'missing' },
      { loc: ['body', 'name'], msg: 'Too short', type: 'string_too_short' },
    ]);
    expect(errors).toEqual({
      'education[0]': 'start_year must not be after end_year',
      name: 'Field required Too short',
    });
  });

  it('returns no errors when details are not a validation list', () => {
    expect(fieldErrorsFromDetails({ from: 'Offer' })).toEqual({});
    expect(fieldErrorsFromDetails(null)).toEqual({});
  });
});

describe('fieldErrorsFromError', () => {
  it('maps a 422 envelope to field errors', () => {
    const error = new ApiError('VALIDATION_ERROR', 'Invalid request.', 422, [
      {
        loc: ['body', 'projects', 1, 'url'],
        msg: 'URL must use http or https',
        type: 'value_error',
      },
    ]);
    expect(fieldErrorsFromError(error)).toEqual({
      'projects[1].url': 'URL must use http or https',
    });
  });

  it('puts the envelope message on email when the email is taken', () => {
    const error = new ApiError('EMAIL_TAKEN', 'That email is already in use.', 409);
    expect(fieldErrorsFromError(error)).toEqual({ email: 'That email is already in use.' });
  });

  it('returns no field errors for other failures', () => {
    expect(fieldErrorsFromError(new ApiError('INTERNAL_ERROR', 'Oops', 500))).toEqual({});
    expect(fieldErrorsFromError(new Error('boom'))).toEqual({});
  });
});

describe('parentFieldPath', () => {
  it('removes the last segment when walking up a path', () => {
    expect(parentFieldPath('projects[1].url')).toBe('projects[1]');
    expect(parentFieldPath('projects[1]')).toBe('projects');
    expect(parentFieldPath('projects')).toBe('');
  });
});

describe('clearFieldErrors', () => {
  const errors = {
    education: 'Too many entries',
    'education[0]': 'start_year must not be after end_year',
    'education[0].start_year': 'Too small',
    'projects[1].url': 'Bad URL',
  };

  it('drops the edited path and its enclosing item but keeps list-level and other errors', () => {
    expect(clearFieldErrors(errors, 'education[0].start_year')).toEqual({
      education: 'Too many entries',
      'projects[1].url': 'Bad URL',
    });
  });

  it('drops every error under a list when the list itself changed', () => {
    expect(clearFieldErrors(errors, 'education')).toEqual({ 'projects[1].url': 'Bad URL' });
  });

  it('returns the same object when nothing is cleared', () => {
    expect(clearFieldErrors(errors, 'name')).toBe(errors);
  });
});

describe('fieldDomId', () => {
  it('builds a valid id for nested paths', () => {
    expect(fieldDomId('projects[1].url')).toBe('field-projects-1-url');
    expect(fieldDomId('technical_skills[0]')).toBe('field-technical-skills-0');
  });
});
