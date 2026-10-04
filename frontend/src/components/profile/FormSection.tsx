import type { ReactNode } from 'react';
import { cx } from '../../lib/classNames';
import { fieldDomId } from '../../lib/validationErrors';
import { FieldError } from '../ui/FieldError';

interface FormSectionProps {
  legend: string;
  description?: string;
  /** Field path whose list-level error is shown under the legend (e.g. `projects`). */
  errorPath?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}

/** One `<fieldset>` section of the profile form, styled as a card. */
export function FormSection({
  legend,
  description,
  errorPath,
  error,
  children,
  className,
}: FormSectionProps) {
  const id = errorPath === undefined ? undefined : fieldDomId(errorPath);
  const descriptionId = id === undefined ? undefined : `${id}-description`;
  const errorId = id === undefined ? undefined : `${id}-error`;
  const hasError = error !== undefined && error !== '';
  const describedBy = cx(description !== undefined && descriptionId, hasError && errorId);
  return (
    <fieldset
      id={id}
      tabIndex={id === undefined ? undefined : -1}
      aria-describedby={describedBy === '' ? undefined : describedBy}
      className={cx('rounded border border-ink-200 bg-white p-5 shadow-sm', className)}
    >
      <legend className="float-left w-full text-base font-semibold text-ink-900">{legend}</legend>
      <div className="clear-both">
        {description !== undefined && (
          <p id={descriptionId} className="mt-0.5 text-sm text-ink-600">
            {description}
          </p>
        )}
        {hasError && errorId !== undefined && <FieldError id={errorId} message={error} />}
        <div className="mt-4 flex flex-col gap-4">{children}</div>
      </div>
    </fieldset>
  );
}
