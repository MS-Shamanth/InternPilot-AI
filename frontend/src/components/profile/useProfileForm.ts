import { useCallback, useMemo, useRef, useState } from 'react';
import { formValuesToUpdate, profileToFormValues } from '../../lib/profileForm';
import type { ProfileFormValues } from '../../lib/profileForm';
import { clearFieldErrors, NO_FIELD_ERRORS } from '../../lib/validationErrors';
import type { FieldErrors } from '../../lib/validationErrors';
import type { Profile, ProfileUpdate } from '../../types/api';

export type SetProfileField = <K extends keyof ProfileFormValues>(
  key: K,
  value: ProfileFormValues[K],
  /** The most specific path that changed (e.g. `projects[1].url`); defaults to `key`. */
  changedPath?: string,
) => void;

export interface ProfileFormState {
  values: ProfileFormValues;
  errors: FieldErrors;
  /** True when the payload would differ from the last loaded or saved profile. */
  isDirty: boolean;
  setField: SetProfileField;
  setErrors: (errors: FieldErrors) => void;
  /** A key for a newly added list item, unique for the lifetime of the form. */
  createItemKey: () => string;
  /** Discards edits and errors; with a profile, that profile becomes the new baseline. */
  reset: (profile?: Profile) => void;
  toUpdate: () => ProfileUpdate;
}

function payloadOf(values: ProfileFormValues): string {
  return JSON.stringify(formValuesToUpdate(values));
}

/** Controlled state for `ProfileForm`: values, last server errors and dirty tracking. */
export function useProfileForm(profile: Profile): ProfileFormState {
  const [baseline, setBaseline] = useState(() => profileToFormValues(profile));
  const [values, setValues] = useState(baseline);
  const [errors, setErrors] = useState<FieldErrors>(NO_FIELD_ERRORS);
  const itemCounter = useRef(0);

  const isDirty = useMemo(() => payloadOf(values) !== payloadOf(baseline), [values, baseline]);

  const setField = useCallback<SetProfileField>((key, value, changedPath) => {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => clearFieldErrors(current, changedPath ?? key));
  }, []);

  const createItemKey = useCallback(() => {
    itemCounter.current += 1;
    return `new-${String(itemCounter.current)}`;
  }, []);

  const reset = useCallback(
    (nextProfile?: Profile) => {
      const nextBaseline = nextProfile === undefined ? baseline : profileToFormValues(nextProfile);
      setBaseline(nextBaseline);
      setValues(nextBaseline);
      setErrors(NO_FIELD_ERRORS);
    },
    [baseline],
  );

  const toUpdate = useCallback(() => formValuesToUpdate(values), [values]);

  return { values, errors, isDirty, setField, setErrors, createItemKey, reset, toUpdate };
}
