import type { ReactNode } from 'react';

import { cx } from '../../lib/classNames';
import { FieldError } from './FieldError';
import type { FieldIds } from './useFieldIds';

interface FieldProps {
  ids: FieldIds;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: ReactNode;
}

/** Stacked label → hint → control → error layout used by TextField, TextArea and Select. */
export function Field({
  ids,
  label,
  hint,
  error,
  required = false,
  className,
  children,
}: FieldProps) {
  return (
    <div className={cx('flex flex-col', className)}>
      <label htmlFor={ids.inputId} className="text-sm font-medium text-ink-800">
        {label}
        {required && <span className="ml-1 text-xs font-normal text-ink-600">(required)</span>}
      </label>
      {hint !== undefined && hint !== '' && (
        <p id={ids.hintId} className="mt-0.5 text-xs text-ink-600">
          {hint}
        </p>
      )}
      <div className="mt-1">{children}</div>
      {ids.hasError && error !== undefined && <FieldError id={ids.errorId} message={error} />}
    </div>
  );
}
