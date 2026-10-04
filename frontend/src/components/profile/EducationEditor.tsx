import { useRef } from 'react';
import { emptyEducation, removeAt, replaceAt } from '../../lib/profileForm';
import type { EducationFormValues } from '../../lib/profileForm';
import { fieldDomId } from '../../lib/validationErrors';
import type { FieldErrors } from '../../lib/validationErrors';
import { Button } from '../ui/Button';
import { TextField } from '../ui/TextField';
import { ListItemFieldset } from './ListItemFieldset';

const PATH = 'education';
const MAX_ENTRIES = 10;
const YEAR_LIMITS = { min: 1950, max: 2100, step: 1 } as const;

type TextKey = Exclude<keyof EducationFormValues, 'key'>;

interface EducationEditorProps {
  entries: readonly EducationFormValues[];
  errors: FieldErrors;
  onChange: (next: EducationFormValues[], changedPath: string) => void;
  createItemKey: () => string;
}

/** Education entries: institution, degree, field of study and years. */
export function EducationEditor({
  entries,
  errors,
  onChange,
  createItemKey,
}: EducationEditorProps) {
  const addButtonRef = useRef<HTMLButtonElement>(null);

  function update(index: number, entry: EducationFormValues, field: TextKey, value: string) {
    onChange(
      replaceAt(entries, index, { ...entry, [field]: value }),
      `${PATH}[${String(index)}].${field}`,
    );
  }

  function handleAdd() {
    onChange([...entries, emptyEducation(createItemKey())], PATH);
  }

  function handleRemove(index: number) {
    onChange(removeAt(entries, index), PATH);
    addButtonRef.current?.focus();
  }

  return (
    <div className="flex flex-col gap-4">
      {entries.length === 0 && <p className="text-sm text-ink-600">No education entries yet.</p>}
      {entries.map((entry, index) => {
        const path = `${PATH}[${String(index)}]`;
        const fieldProps = (field: TextKey) => ({
          id: fieldDomId(`${path}.${field}`),
          value: entry[field],
          error: errors[`${path}.${field}`],
          onChange: (event: { target: { value: string } }) => {
            update(index, entry, field, event.target.value);
          },
        });
        return (
          <ListItemFieldset
            key={entry.key}
            legend={`Education ${String(index + 1)}`}
            path={path}
            error={errors[path]}
            onRemove={() => {
              handleRemove(index);
            }}
          >
            <TextField
              label="Institution"
              required
              maxLength={150}
              {...fieldProps('institution')}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label="Degree" maxLength={100} {...fieldProps('degree')} />
              <TextField label="Field of study" maxLength={100} {...fieldProps('field')} />
              <TextField
                label="Start year"
                type="number"
                {...YEAR_LIMITS}
                {...fieldProps('start_year')}
              />
              <TextField
                label="End year"
                type="number"
                {...YEAR_LIMITS}
                {...fieldProps('end_year')}
              />
            </div>
          </ListItemFieldset>
        );
      })}
      <div>
        <Button
          ref={addButtonRef}
          variant="secondary"
          onClick={handleAdd}
          disabled={entries.length >= MAX_ENTRIES}
        >
          Add education
        </Button>
      </div>
    </div>
  );
}
