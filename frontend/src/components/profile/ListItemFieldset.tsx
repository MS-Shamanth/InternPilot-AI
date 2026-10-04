import type { ReactNode } from 'react';
import { fieldDomId } from '../../lib/validationErrors';
import { Button } from '../ui/Button';
import { FieldError } from '../ui/FieldError';

interface ListItemFieldsetProps {
  /** e.g. "Project 2"; also names the remove button ("Remove project 2"). */
  legend: string;
  /** Field path of the item, e.g. `projects[1]`; item-level errors are shown under the legend. */
  path: string;
  error?: string;
  onRemove: () => void;
  children: ReactNode;
}

/** One entry of a list editor (project, education, certification) with its remove action. */
export function ListItemFieldset({
  legend,
  path,
  error,
  onRemove,
  children,
}: ListItemFieldsetProps) {
  const id = fieldDomId(path);
  const errorId = `${id}-error`;
  const hasError = error !== undefined && error !== '';
  return (
    <fieldset
      id={id}
      tabIndex={-1}
      aria-describedby={hasError ? errorId : undefined}
      className="relative rounded border border-ink-200 bg-ink-50 p-4"
    >
      <legend className="float-left py-1 text-sm font-semibold text-ink-800">{legend}</legend>
      {/* Outside the legend so the group's accessible name stays just the legend text. */}
      <Button variant="ghost" size="sm" onClick={onRemove} className="absolute right-3 top-3">
        Remove<span className="sr-only"> {legend.toLowerCase()}</span>
      </Button>
      <div className="clear-both flex flex-col gap-3 pt-2">
        {hasError && <FieldError id={errorId} message={error} />}
        {children}
      </div>
    </fieldset>
  );
}
