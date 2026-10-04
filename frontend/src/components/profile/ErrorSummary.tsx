import { forwardRef, useId } from 'react';
import type { MouseEvent } from 'react';
import { fieldDomId, parentFieldPath } from '../../lib/validationErrors';
import type { FieldErrors } from '../../lib/validationErrors';

interface ErrorSummaryProps {
  errors: FieldErrors;
  /** Human label for a field path, e.g. "Project 2 · URL". */
  labelFor: (path: string) => string;
}

/** Focuses the control for `path`, or its nearest rendered ancestor (list item, section). */
function focusField(path: string): void {
  for (let current = path; ; current = parentFieldPath(current)) {
    const element = document.getElementById(fieldDomId(current));
    if (element !== null) {
      element.focus();
      return;
    }
    if (current === '') {
      return;
    }
  }
}

/** "There is a problem" box listing every server error with a link to its field. */
export const ErrorSummary = forwardRef<HTMLDivElement, ErrorSummaryProps>(function ErrorSummary(
  { errors, labelFor },
  ref,
) {
  const titleId = useId();
  const entries = Object.entries(errors);

  function handleClick(event: MouseEvent<HTMLAnchorElement>, path: string) {
    event.preventDefault();
    focusField(path);
  }

  return (
    <div
      ref={ref}
      role="alert"
      tabIndex={-1}
      aria-labelledby={titleId}
      className="rounded border border-danger-700 bg-danger-50 p-4"
    >
      <h2 id={titleId} className="text-base font-semibold text-danger-800">
        {entries.length === 1
          ? 'There is 1 problem with your profile'
          : `There are ${String(entries.length)} problems with your profile`}
      </h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {entries.map(([path, message]) => (
          <li key={path}>
            <a
              href={`#${fieldDomId(path)}`}
              className="font-medium text-danger-800 underline"
              onClick={(event) => {
                handleClick(event, path);
              }}
            >
              {labelFor(path)}: {message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
});
