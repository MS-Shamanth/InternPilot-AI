import { forwardRef } from 'react';
import type { TextareaHTMLAttributes } from 'react';

import { Field } from './Field';
import { controlClasses, useFieldIds } from './useFieldIds';

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
  error?: string;
  wrapperClassName?: string;
}

/** Labelled multi-line input with optional hint and an `aria-invalid` error message. */
export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  {
    label,
    hint,
    error,
    id,
    required,
    rows = 4,
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
      <textarea
        ref={ref}
        id={ids.inputId}
        rows={rows}
        required={required}
        aria-invalid={ids.hasError || undefined}
        aria-describedby={ids.describedBy}
        className={controlClasses(ids.hasError, className)}
        {...rest}
      />
    </Field>
  );
});
