/**
 * Maps server validation failures onto form field paths (design.md §8.1, §8.2).
 *
 * A field path names one control in a form, e.g. `name`, `technical_skills[3]` or
 * `projects[1].url`; the backend's `loc` (`["body", "projects", 1, "url"]`) maps onto it.
 * The server stays the source of truth: these helpers only decide where to show its messages.
 */
import { isApiError } from '../api/client';
import type { ApiErrorDetails, ValidationErrorItem } from '../types/api';

/** Error message per field path, in the order the server reported them. `''` = whole form. */
export type FieldErrors = Readonly<Record<string, string>>;

export const NO_FIELD_ERRORS: FieldErrors = {};

const VALIDATION_STATUS = 422;
const EMAIL_TAKEN = 'EMAIL_TAKEN';
const REQUEST_ROOT = 'body';
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;
/** Pydantic prefixes custom validator messages with the error kind; users do not need it. */
const MESSAGE_PREFIX = /^(Value error|Assertion failed), /;
/** The last `.name`, `[n]` or leading `name` of a field path. */
const LAST_SEGMENT = /(?:^|\.)[A-Za-z_][A-Za-z0-9_]*$|\[\d+\]$/;

/**
 * `["body", "projects", 1, "url"]` → `projects[1].url`.
 *
 * The leading `body` is dropped; numbers become `[n]`; strings that are not identifiers
 * (Pydantic union/validator tags such as `function-after[...]`) are skipped.
 */
export function locToFieldPath(loc: readonly (string | number)[]): string {
  const parts = loc[0] === REQUEST_ROOT ? loc.slice(1) : loc;
  let path = '';
  for (const part of parts) {
    if (typeof part === 'number') {
      path += `[${String(part)}]`;
    } else if (IDENTIFIER.test(part)) {
      path += path === '' ? part : `.${part}`;
    }
  }
  return path;
}

function cleanMessage(message: string): string {
  return message.replace(MESSAGE_PREFIX, '');
}

function isValidationList(details: ApiErrorDetails): details is ValidationErrorItem[] {
  return Array.isArray(details);
}

/** Groups a 422 `details` list by field path; several messages for one path are joined. */
export function fieldErrorsFromDetails(details: ApiErrorDetails): FieldErrors {
  if (!isValidationList(details)) {
    return NO_FIELD_ERRORS;
  }
  const errors: Record<string, string> = {};
  for (const item of details) {
    const path = locToFieldPath(item.loc);
    const message = cleanMessage(item.msg);
    const existing = errors[path];
    errors[path] = existing === undefined ? message : `${existing} ${message}`;
  }
  return errors;
}

/**
 * Field errors for a failed profile save: per-field 422 messages, the envelope message on
 * `email` for 409 `EMAIL_TAKEN`, and nothing for other failures (they are shown as toasts).
 */
export function fieldErrorsFromError(error: unknown): FieldErrors {
  if (!isApiError(error)) {
    return NO_FIELD_ERRORS;
  }
  if (error.code === EMAIL_TAKEN) {
    return { email: error.message };
  }
  if (error.status === VALIDATION_STATUS) {
    return fieldErrorsFromDetails(error.details);
  }
  return NO_FIELD_ERRORS;
}

/** `projects[1].url` → `projects[1]` → `projects` → `''`. */
export function parentFieldPath(path: string): string {
  return path.replace(LAST_SEGMENT, '');
}

function isUnder(path: string, ancestor: string): boolean {
  return path === ancestor || path.startsWith(`${ancestor}.`) || path.startsWith(`${ancestor}[`);
}

/**
 * Errors that still apply after the value at `changedPath` was edited: the path itself, its
 * descendants and its enclosing list items (e.g. `education[0]` for a year-order error) are
 * dropped; list-level errors (e.g. "too many items") and unrelated fields are kept.
 */
export function clearFieldErrors(errors: FieldErrors, changedPath: string): FieldErrors {
  const enclosingItems = new Set<string>();
  for (let parent = parentFieldPath(changedPath); parent !== ''; parent = parentFieldPath(parent)) {
    if (parent.endsWith(']')) {
      enclosingItems.add(parent);
    }
  }
  const remaining = Object.entries(errors).filter(
    ([path]) => !isUnder(path, changedPath) && !enclosingItems.has(path),
  );
  return remaining.length === Object.keys(errors).length ? errors : Object.fromEntries(remaining);
}

/** Stable DOM id for the control at a field path, used for labels and error-summary links. */
export function fieldDomId(path: string): string {
  return `field-${path.replace(/[^A-Za-z0-9]+/g, '-').replace(/-+$/, '')}`;
}
