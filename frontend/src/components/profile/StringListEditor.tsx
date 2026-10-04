import { useId, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { removeAt } from '../../lib/profileForm';
import { fieldDomId } from '../../lib/validationErrors';
import type { FieldErrors } from '../../lib/validationErrors';
import { Button } from '../ui/Button';
import { FieldError } from '../ui/FieldError';
import { IconButton } from '../ui/IconButton';
import { TextField } from '../ui/TextField';

interface StringListEditorProps {
  /** Group legend, e.g. "Technical skills". */
  legend: string;
  /** Singular noun for the add control, e.g. "technical skill". */
  itemLabel: string;
  /** Field path of the list, e.g. `technical_skills` or `projects[0].technologies`. */
  path: string;
  values: readonly string[];
  errors: FieldErrors;
  /** `changedPath` is always the list itself: removing an item shifts the indexes after it. */
  onChange: (next: string[], changedPath: string) => void;
  maxItems: number;
  maxItemLength: number;
  hint?: string;
}

/** Editable list of short strings: add with Enter or the Add button, remove per item. */
export function StringListEditor({
  legend,
  itemLabel,
  path,
  values,
  errors,
  onChange,
  maxItems,
  maxItemLength,
  hint,
}: StringListEditorProps) {
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const legendId = useId();

  const trimmedDraft = draft.trim();
  const isFull = values.length >= maxItems;
  const canAdd = trimmedDraft !== '' && !isFull;
  const limitHint = `Up to ${String(maxItems)}. Press Enter to add.`;

  function addDraft() {
    if (!canAdd) {
      return;
    }
    onChange([...values, trimmedDraft], path);
    setDraft('');
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      // Enter adds the item instead of submitting the whole form.
      event.preventDefault();
      addDraft();
    }
  }

  function handleRemove(index: number) {
    onChange(removeAt(values, index), path);
    inputRef.current?.focus();
  }

  return (
    <fieldset className="flex flex-col gap-2">
      <legend id={legendId} className="text-sm font-semibold text-ink-800">
        {legend}
      </legend>
      {values.length === 0 ? (
        <p className="text-sm text-ink-600">No {legend.toLowerCase()} yet.</p>
      ) : (
        <ul aria-labelledby={legendId} className="flex flex-wrap gap-2">
          {values.map((value, index) => {
            const itemPath = `${path}[${String(index)}]`;
            const itemId = fieldDomId(itemPath);
            const itemError = errors[itemPath];
            return (
              <li
                key={`${value}-${String(index)}`}
                id={itemId}
                tabIndex={-1}
                className={
                  itemError === undefined
                    ? 'flex items-center gap-1 rounded border border-ink-300 bg-ink-50 py-0.5 pl-2 pr-0.5 text-sm text-ink-800'
                    : 'flex flex-col rounded border border-danger-700 bg-danger-50 px-2 py-1 text-sm text-ink-800'
                }
              >
                <span className="flex items-center gap-1">
                  <span>{value}</span>
                  <IconButton
                    aria-label={`Remove ${value}`}
                    aria-describedby={itemError === undefined ? undefined : `${itemId}-error`}
                    icon="×"
                    size="sm"
                    onClick={() => {
                      handleRemove(index);
                    }}
                  />
                </span>
                {itemError !== undefined && (
                  <FieldError id={`${itemId}-error`} message={itemError} />
                )}
              </li>
            );
          })}
        </ul>
      )}
      <div className="flex items-end gap-2">
        <TextField
          ref={inputRef}
          id={fieldDomId(path)}
          label={`Add ${itemLabel}`}
          hint={hint === undefined ? limitHint : `${hint} ${limitHint}`}
          error={errors[path]}
          value={draft}
          maxLength={maxItemLength}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
          onKeyDown={handleKeyDown}
          wrapperClassName="flex-1"
        />
        <Button variant="secondary" onClick={addDraft} disabled={!canAdd}>
          Add<span className="sr-only"> {itemLabel}</span>
        </Button>
      </div>
    </fieldset>
  );
}
