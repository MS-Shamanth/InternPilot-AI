import { useRef } from 'react';
import { emptyCertification, removeAt, replaceAt } from '../../lib/profileForm';
import type { CertificationFormValues } from '../../lib/profileForm';
import { fieldDomId } from '../../lib/validationErrors';
import type { FieldErrors } from '../../lib/validationErrors';
import { Button } from '../ui/Button';
import { TextField } from '../ui/TextField';
import { FormSection } from './FormSection';
import { ListItemFieldset } from './ListItemFieldset';

const PATH = 'certifications';
const MAX_CERTIFICATIONS = 30;

type TextKey = Exclude<keyof CertificationFormValues, 'key'>;

interface CertificationsEditorProps {
  certifications: readonly CertificationFormValues[];
  errors: FieldErrors;
  onChange: (next: CertificationFormValues[], changedPath: string) => void;
  createItemKey: () => string;
}

/** Certifications list: name, issuer and year. */
export function CertificationsEditor({
  certifications,
  errors,
  onChange,
  createItemKey,
}: CertificationsEditorProps) {
  const addButtonRef = useRef<HTMLButtonElement>(null);

  function update(
    index: number,
    certification: CertificationFormValues,
    field: TextKey,
    value: string,
  ) {
    onChange(
      replaceAt(certifications, index, { ...certification, [field]: value }),
      `${PATH}[${String(index)}].${field}`,
    );
  }

  function handleAdd() {
    onChange([...certifications, emptyCertification(createItemKey())], PATH);
  }

  function handleRemove(index: number) {
    onChange(removeAt(certifications, index), PATH);
    addButtonRef.current?.focus();
  }

  return (
    <FormSection legend="Certifications" errorPath={PATH} error={errors[PATH]}>
      {certifications.length === 0 && (
        <p className="text-sm text-ink-600">No certifications yet.</p>
      )}
      {certifications.map((certification, index) => {
        const path = `${PATH}[${String(index)}]`;
        const fieldProps = (field: TextKey) => ({
          id: fieldDomId(`${path}.${field}`),
          value: certification[field],
          error: errors[`${path}.${field}`],
          onChange: (event: { target: { value: string } }) => {
            update(index, certification, field, event.target.value);
          },
        });
        return (
          <ListItemFieldset
            key={certification.key}
            legend={`Certification ${String(index + 1)}`}
            path={path}
            error={errors[path]}
            onRemove={() => {
              handleRemove(index);
            }}
          >
            <TextField
              label="Certification name"
              required
              maxLength={120}
              {...fieldProps('name')}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label="Issuer" maxLength={120} {...fieldProps('issuer')} />
              <TextField
                label="Year"
                type="number"
                min={1950}
                max={2100}
                step={1}
                {...fieldProps('year')}
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
          disabled={certifications.length >= MAX_CERTIFICATIONS}
        >
          Add certification
        </Button>
      </div>
    </FormSection>
  );
}
