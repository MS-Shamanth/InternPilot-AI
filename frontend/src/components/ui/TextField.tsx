import { forwardRef } from 'react';
import type { InputHTMLAttributes } from 'react';

import { Field } from './Field';
import { controlClasses, useFieldIds } from './useFieldIds';

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
  hint?: string;
  error?: string;
  type?:
    'text' | 'email' | 'url' | 'search' | 'number' | 'date' | 'datetime-local' | 'password' | 'tel';
  /** Classes for the wrapper (label + control + messages). */
  wrapperClassName?: string;
}

/** Labelled single-line input with optional hint and an `aria-invalid` error message. */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  {
    label,
    hint,
    error,
    id,
    type = 'text',
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
    <Field
      ids={ids}
      label={label}
      hint={hint}
      error={error}
      required={required}
      className={wrapperClassName}
    >
      <input
        ref={ref}
        id={ids.inputId}
        type={type}
        required={required}
        aria-invalid={ids.hasError || undefined}
        aria-describedby={ids.describedBy}
        className={controlClasses(ids.hasError, className)}
        {...rest}
      />
    </Field>
  );
});
