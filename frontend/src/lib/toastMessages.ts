import { isApiError } from '../api/client';

export const UNEXPECTED_ERROR_MESSAGE = 'Something went wrong. Please try again.';

const INVALID_STATUS_TRANSITION = 'INVALID_STATUS_TRANSITION';

function allowedTargets(details: unknown): string[] | null {
  if (typeof details !== 'object' || details === null || Array.isArray(details)) {
    return null;
  }
  const allowed = (details as Record<string, unknown>).allowed;
  if (!Array.isArray(allowed)) {
    return null;
  }
  return allowed.filter((item): item is string => typeof item === 'string');
}

/**
 * User-facing text for a failed operation (design.md §15.2): the envelope `message` of an
 * `ApiError`, plus the allowed targets for a rejected status transition.
 */
export function toastErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return UNEXPECTED_ERROR_MESSAGE;
  }
  if (error.code !== INVALID_STATUS_TRANSITION) {
    return error.message;
  }
  const allowed = allowedTargets(error.details);
  if (allowed === null) {
    return error.message;
  }
  const suffix =
    allowed.length > 0 ? `Allowed moves: ${allowed.join(', ')}.` : 'No further moves are allowed.';
  return `${error.message.replace(/\.+$/, '')}. ${suffix}`;
}
