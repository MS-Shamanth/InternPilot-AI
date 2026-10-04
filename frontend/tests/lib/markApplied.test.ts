import { describe, expect, it } from 'vitest';
import { markAppliedState } from '../../src/lib/markApplied';
import { APPLICATIONS_META } from '../jobs/jobFixtures';

describe('markAppliedState', () => {
  it('is available without an application or when meta allows a move to Applied', () => {
    expect(markAppliedState(null, APPLICATIONS_META.transitions).available).toBe(true);
    expect(markAppliedState('Saved', APPLICATIONS_META.transitions).available).toBe(true);
    expect(markAppliedState('Interested', APPLICATIONS_META.transitions).available).toBe(true);
  });

  it('is unavailable with a reason when already applied or the move is not allowed', () => {
    expect(markAppliedState('Applied', APPLICATIONS_META.transitions)).toEqual({
      available: false,
      reason: 'Already marked as applied.',
    });
    expect(markAppliedState('Offer', APPLICATIONS_META.transitions)).toEqual({
      available: false,
      reason: 'This application is Offer; it cannot move to Applied.',
    });
  });

  it('lets the server decide while the transition table is unknown', () => {
    expect(markAppliedState('Offer', undefined).available).toBe(true);
  });
});
