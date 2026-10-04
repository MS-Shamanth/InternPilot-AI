import { forwardRef } from 'react';
import type { InputHTMLAttributes } from 'react';

import { cx } from '../../lib/classNames';
import { FieldError } from './FieldError';
import { useFieldIds } from './useFieldIds';

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
  hint?: string;
  error?: string;
  wrapperClassName?: string;
}

/** Native checkbox with its label to the right and optional hint/error below. */
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  {
    label,
    hint,
    error,
    id,
    required,
    className,
    wrapperClassName,
    'aria-describedby': describedBy,
    ...rest
  },
  ref,
) {
  const ids = useFieldIds({ id, hint, error, describedBy });
  return (
    <div className={wrapperClassName}>
      <div className="flex items-start gap-2">
        <input
          ref={ref}
          id={ids.inputId}
          type="checkbox"
          required={required}
          aria-invalid={ids.hasError || undefined}
          aria-describedby={ids.describedBy}
          className={cx(
            'mt-0.5 h-4 w-4 shrink-0 rounded border-ink-400 accent-pilot-700 disabled:cursor-not-allowed',
            className,
          )}
          {...rest}
        />
        <div className="min-w-0">
          <label htmlFor={ids.inputId} className="text-sm font-medium text-ink-800">
            {label}
            {required === true && (
              <span className="ml-1 text-xs font-normal text-ink-600">(required)</span>
            )}
          </label>
          {hint !== undefined && hint !== '' && (
            <p id={ids.hintId} className="text-xs text-ink-600">
              {hint}
            </p>
          )}
        </div>
      </div>
      {ids.hasError && error !== undefined && <FieldError id={ids.errorId} message={error} />}
    </div>
  );
});
