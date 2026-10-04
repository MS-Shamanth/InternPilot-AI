import { forwardRef } from 'react';
import type { SelectHTMLAttributes } from 'react';

import { Field } from './Field';
import { controlClasses, useFieldIds } from './useFieldIds';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: string;
  error?: string;
  wrapperClassName?: string;
}

/** Labelled native `<select>`; pass `<option>` elements as children. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  {
    label,
    hint,
    error,
    id,
    required,
    className,
    wrapperClassName,
    children,
    'aria-describedby': describedBy,
    ...rest
  },
  ref,
) {
  const ids = useFieldIds({ id, hint, error, describedBy });
  return (
    <Field
      ids={ids}
      label={label}
      hint={hint}
      error={error}
      required={required}
      className={wrapperClassName}
    >
      <select
        ref={ref}
        id={ids.inputId}
        required={required}
        aria-invalid={ids.hasError || undefined}
        aria-describedby={ids.describedBy}
        className={controlClasses(ids.hasError, className)}
        {...rest}
      >
        {children}
      </select>
    </Field>
  );
});
