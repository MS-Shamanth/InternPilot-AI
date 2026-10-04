import { useId } from 'react';

import { cx } from '../../lib/classNames';

interface FieldIdOptions {
  id?: string;
  hint?: string;
  error?: string;
  /** Extra ids the caller wants in `aria-describedby`. */
  describedBy?: string;
}

export interface FieldIds {
  inputId: string;
  hintId: string;
  errorId: string;
  /** Hint, error and caller ids joined, or undefined when there are none. */
  describedBy: string | undefined;
  hasError: boolean;
}

/** Stable ids that tie a control to its `<label>`, hint and error message. */
export function useFieldIds({ id, hint, error, describedBy }: FieldIdOptions): FieldIds {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const hasError = error !== undefined && error !== '';
  const joined = cx(hint !== undefined && hint !== '' && hintId, hasError && errorId, describedBy);
  return {
    inputId,
    hintId,
    errorId,
    describedBy: joined === '' ? undefined : joined,
    hasError,
  };
}

/** Shared look for text-like controls; the error state adds a border change and text. */
export function controlClasses(hasError: boolean, className?: string): string {
  return cx(
    'block w-full rounded border bg-white px-3 py-2 text-sm text-ink-900 placeholder:text-ink-600 disabled:cursor-not-allowed disabled:bg-ink-100 disabled:text-ink-600',
    hasError ? 'border-danger-700' : 'border-ink-300',
    className,
  );
}
