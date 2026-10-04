/**
 * Allowed application moves, read from `GET /applications/meta` (R5.4, R5.10).
 *
 * The transition table lives in the backend (`application_status.py`); these helpers only
 * look it up, so the UI never offers a move the server would reject.
 */
import type { ApplicationStatus, ApplicationsMeta } from '../types/api';

/** Statuses `status` may move to, in the server's (canonical) order. */
export function allowedTargets(
  meta: ApplicationsMeta,
  status: ApplicationStatus,
): ApplicationStatus[] {
  // A status missing from the map (an older or newer backend) has no known moves.
  const transitions: Partial<ApplicationsMeta['transitions']> = meta.transitions;
  return transitions[status] ?? [];
}

/** Whether `from` → `to` is an actual, allowed move (a same-status "move" is not). */
export function canMove(
  meta: ApplicationsMeta,
  from: ApplicationStatus,
  to: ApplicationStatus,
): boolean {
  return from !== to && allowedTargets(meta, from).includes(to);
}

/** Choices for a per-row status control: the current status plus its targets, canonical order. */
export function statusChoices(
  meta: ApplicationsMeta,
  current: ApplicationStatus,
): ApplicationStatus[] {
  const targets = allowedTargets(meta, current);
  const choices = meta.statuses.filter((status) => status === current || targets.includes(status));
  return choices.includes(current) ? choices : [current, ...choices];
}
