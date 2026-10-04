import { describe, expect, it } from 'vitest';

import { ApiError } from '../../src/api/client';
import { UNEXPECTED_ERROR_MESSAGE, toastErrorMessage } from '../../src/lib/toastMessages';

describe('toastErrorMessage', () => {
  it('returns the envelope message when given an ApiError', () => {
    const error = new ApiError('DUPLICATE_APPLICATION', 'An application already exists', 409);

    expect(toastErrorMessage(error)).toBe('An application already exists');
  });

  it('appends the allowed targets when a status transition is rejected', () => {
    const error = new ApiError(
      'INVALID_STATUS_TRANSITION',
      'Cannot move from Offer to Applied',
      409,
      {
        from: 'Offer',
        to: 'Applied',
        allowed: ['Withdrawn'],
      },
    );

    expect(toastErrorMessage(error)).toBe(
      'Cannot move from Offer to Applied. Allowed moves: Withdrawn.',
    );
  });

  it('says no moves are allowed when the allowed list is empty', () => {
    const error = new ApiError('INVALID_STATUS_TRANSITION', 'Cannot move from Rejected.', 409, {
      allowed: [],
    });

    expect(toastErrorMessage(error)).toBe(
      'Cannot move from Rejected. No further moves are allowed.',
    );
  });

  it('returns a generic message when the error is not an ApiError', () => {
    expect(toastErrorMessage(new TypeError('boom'))).toBe(UNEXPECTED_ERROR_MESSAGE);
  });
});
