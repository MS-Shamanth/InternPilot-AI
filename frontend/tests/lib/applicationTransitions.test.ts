import { describe, expect, it } from 'vitest';
import { allowedTargets, canMove, statusChoices } from '../../src/lib/applicationTransitions';
import type { ApplicationsMeta } from '../../src/types/api';
import { APPLICATIONS_META } from '../jobs/jobFixtures';

/** A different table than the backend's, to show nothing is hard-coded in the frontend. */
const CUSTOM_META = {
  statuses: ['Saved', 'Applied', 'Offer'],
  transitions: { Saved: ['Offer'], Applied: [], Offer: ['Saved'] },
} as unknown as ApplicationsMeta;

describe('allowedTargets', () => {
  it('returns the targets from meta in their order', () => {
    expect(allowedTargets(APPLICATIONS_META, 'Applied')).toEqual([
      'Assessment',
      'Interview',
      'Rejected',
      'Offer',
      'Withdrawn',
    ]);
  });

  it('follows whatever table meta provides', () => {
    expect(allowedTargets(CUSTOM_META, 'Saved')).toEqual(['Offer']);
  });

  it('returns no targets when meta does not list the status', () => {
    expect(allowedTargets(CUSTOM_META, 'Interview')).toEqual([]);
  });
});

describe('canMove', () => {
  it('allows a move listed in meta', () => {
    expect(canMove(APPLICATIONS_META, 'Saved', 'Applied')).toBe(true);
  });

  it('rejects a move not listed in meta', () => {
    expect(canMove(APPLICATIONS_META, 'Offer', 'Applied')).toBe(false);
    expect(canMove(CUSTOM_META, 'Saved', 'Applied')).toBe(false);
  });

  it('treats a same-status move as not a move', () => {
    expect(canMove(APPLICATIONS_META, 'Interview', 'Interview')).toBe(false);
  });
});

describe('statusChoices', () => {
  it('lists the current status and its targets in canonical order', () => {
    expect(statusChoices(APPLICATIONS_META, 'Interview')).toEqual([
      'Assessment',
      'Interview',
      'Rejected',
      'Offer',
      'Withdrawn',
    ]);
  });

  it('keeps the current status when meta has no moves or does not list it', () => {
    expect(statusChoices(CUSTOM_META, 'Applied')).toEqual(['Applied']);
    expect(statusChoices(CUSTOM_META, 'Interview')).toEqual(['Interview']);
  });
});
