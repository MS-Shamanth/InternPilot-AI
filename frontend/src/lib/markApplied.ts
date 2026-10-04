/**
 * Whether "Mark as applied" makes sense for a job's current application (R2.10, R2.11).
 *
 * The rule is not duplicated here: it reads the server's transition table from
 * `GET /applications/meta`. Without the table the action stays available and the server
 * decides (a 409 `INVALID_STATUS_TRANSITION` is shown as a toast).
 */
import type { ApplicationStatus, ApplicationsMeta } from '../types/api';

const APPLIED: ApplicationStatus = 'Applied';

export interface MarkAppliedState {
  available: boolean;
  /** Why the action is unavailable; `null` when it is available. */
  reason: string | null;
}

export function markAppliedState(
  status: ApplicationStatus | null,
  transitions: ApplicationsMeta['transitions'] | undefined,
): MarkAppliedState {
  if (status === APPLIED) {
    return { available: false, reason: 'Already marked as applied.' };
  }
  if (status === null || transitions === undefined || transitions[status].includes(APPLIED)) {
    return { available: true, reason: null };
  }
  return {
    available: false,
    reason: `This application is ${status}; it cannot move to ${APPLIED}.`,
  };
}
