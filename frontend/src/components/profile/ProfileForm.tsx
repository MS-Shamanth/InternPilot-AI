import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import {
  EDUCATION_LEVEL_OPTIONS,
  EXPERIENCE_LEVEL_OPTIONS,
  parseOption,
  profileFieldLabel,
  toggleWorkMode,
  WORK_MODE_OPTIONS,
} from '../../lib/profileForm';
import { fieldDomId, fieldErrorsFromError } from '../../lib/validationErrors';
import type { Profile, ProfileUpdate } from '../../types/api';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { FieldError } from '../ui/FieldError';
import { Select } from '../ui/Select';
import { TextArea } from '../ui/TextArea';
import { TextField } from '../ui/TextField';
import { CertificationsEditor } from './CertificationsEditor';
import { EducationEditor } from './EducationEditor';
import { ErrorSummary } from './ErrorSummary';
import { FormSection } from './FormSection';
import { ProjectsEditor } from './ProjectsEditor';
import { StringListEditor } from './StringListEditor';
import { useProfileForm } from './useProfileForm';

interface ProfileFormProps {
  profile: Profile;
  /** Sends the full replace; resolves with the stored profile or rejects with the failure. */
  onSave: (update: ProfileUpdate) => Promise<Profile>;
  isSaving: boolean;
}

const WORK_MODES_PATH = 'preferred_work_modes';

/** Full profile editor (R1.1); server validation errors appear next to their fields (R1.4). */
export function ProfileForm({ profile, onSave, isSaving }: ProfileFormProps) {
  const form = useProfileForm(profile);
  const summaryRef = useRef<HTMLDivElement>(null);
  const [summaryFocusRequest, setSummaryFocusRequest] = useState(0);

  useEffect(() => {
    if (summaryFocusRequest > 0) {
      summaryRef.current?.focus();
    }
  }, [summaryFocusRequest]);

  const { values, errors, setField } = form;
  const hasErrors = Object.keys(errors).length > 0;
  const workModesError = errors[WORK_MODES_PATH];
  const workModesErrorId = `${fieldDomId(WORK_MODES_PATH)}-error`;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const saved = await onSave(form.toUpdate());
      form.reset(saved);
    } catch (error) {
      const fieldErrors = fieldErrorsFromError(error);
      form.setErrors(fieldErrors);
      if (Object.keys(fieldErrors).length > 0) {
        setSummaryFocusRequest((count) => count + 1);
      }
    }
  }

  function handleReset() {
    form.reset();
  }

  return (
    <form
      aria-label="Profile"
      className="flex flex-col gap-6"
      onSubmit={(event) => {
        void handleSubmit(event);
      }}
    >
      {hasErrors && <ErrorSummary ref={summaryRef} errors={errors} labelFor={profileFieldLabel} />}

      <FormSection legend="Basics">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            id={fieldDomId('name')}
            label="Name"
            required
            maxLength={100}
            autoComplete="name"
            value={values.name}
            error={errors.name}
            onChange={(event) => {
              setField('name', event.target.value);
            }}
          />
          <TextField
            id={fieldDomId('email')}
            label="Email"
            type="email"
            required
            maxLength={254}
            autoComplete="email"
            value={values.email}
            error={errors.email}
            onChange={(event) => {
              setField('email', event.target.value);
            }}
          />
          <TextField
            id={fieldDomId('location')}
            label="Location"
            hint="Where you live now, e.g. Berlin, Germany."
            maxLength={120}
            value={values.location}
            error={errors.location}
            onChange={(event) => {
              setField('location', event.target.value);
            }}
          />
        </div>
      </FormSection>

      <FormSection
        legend="Career preferences"
        description="Target roles, locations, work modes and level are matched against each job."
      >
        <StringListEditor
          legend="Target roles"
          itemLabel="target role"
          path="target_roles"
          values={values.target_roles}
          errors={errors}
          maxItems={10}
          maxItemLength={80}
          onChange={(next, changedPath) => {
            setField('target_roles', next, changedPath);
          }}
        />
        <StringListEditor
          legend="Preferred locations"
          itemLabel="preferred location"
          path="preferred_locations"
          values={values.preferred_locations}
          errors={errors}
          maxItems={10}
          maxItemLength={80}
          onChange={(next, changedPath) => {
            setField('preferred_locations', next, changedPath);
          }}
        />
        <fieldset
          id={fieldDomId(WORK_MODES_PATH)}
          tabIndex={-1}
          aria-describedby={workModesError === undefined ? undefined : workModesErrorId}
          className="flex flex-col gap-2"
        >
          <legend className="text-sm font-semibold text-ink-800">Preferred work modes</legend>
          <div className="flex flex-wrap gap-4">
            {WORK_MODE_OPTIONS.map((option) => (
              <Checkbox
                key={option.value}
                label={option.label}
                checked={values.preferred_work_modes.includes(option.value)}
                onChange={(event) => {
                  setField(
                    'preferred_work_modes',
                    toggleWorkMode(values.preferred_work_modes, option.value, event.target.checked),
                  );
                }}
              />
            ))}
          </div>
          {workModesError !== undefined && (
            <FieldError id={workModesErrorId} message={workModesError} />
          )}
        </fieldset>
        <Select
          id={fieldDomId('experience_level')}
          label="Experience level"
          value={values.experience_level}
          error={errors.experience_level}
          wrapperClassName="sm:max-w-xs"
          onChange={(event) => {
            setField('experience_level', parseOption(EXPERIENCE_LEVEL_OPTIONS, event.target.value));
          }}
        >
          <option value="">Not specified</option>
          {EXPERIENCE_LEVEL_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </FormSection>

      <FormSection legend="Education" errorPath="education" error={errors.education}>
        <Select
          id={fieldDomId('education_level')}
          label="Education level"
          hint="Your highest completed or current level."
          value={values.education_level}
          error={errors.education_level}
          wrapperClassName="sm:max-w-xs"
          onChange={(event) => {
            setField('education_level', parseOption(EDUCATION_LEVEL_OPTIONS, event.target.value));
          }}
        >
          <option value="">Not specified</option>
          {EDUCATION_LEVEL_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        <EducationEditor
          entries={values.education}
          errors={errors}
          createItemKey={form.createItemKey}
          onChange={(next, changedPath) => {
            setField('education', next, changedPath);
          }}
        />
      </FormSection>

      <FormSection
        legend="Skills"
        description="Skills are stored once each; the saved list shows their canonical names."
      >
        <StringListEditor
          legend="Technical skills"
          itemLabel="technical skill"
          path="technical_skills"
          values={values.technical_skills}
          errors={errors}
          maxItems={100}
          maxItemLength={50}
          onChange={(next, changedPath) => {
            setField('technical_skills', next, changedPath);
          }}
        />
        <StringListEditor
          legend="Soft skills"
          itemLabel="soft skill"
          path="soft_skills"
          values={values.soft_skills}
          errors={errors}
          maxItems={50}
          maxItemLength={50}
          onChange={(next, changedPath) => {
            setField('soft_skills', next, changedPath);
          }}
        />
      </FormSection>

      <ProjectsEditor
        projects={values.projects}
        errors={errors}
        createItemKey={form.createItemKey}
        onChange={(next, changedPath) => {
          setField('projects', next, changedPath);
        }}
      />

      <CertificationsEditor
        certifications={values.certifications}
        errors={errors}
        createItemKey={form.createItemKey}
        onChange={(next, changedPath) => {
          setField('certifications', next, changedPath);
        }}
      />

      <FormSection legend="Resume">
        <TextArea
          id={fieldDomId('resume_text')}
          label="Resume text"
          hint="Paste your resume as plain text. Resume analysis uses it by default."
          rows={10}
          maxLength={50000}
          value={values.resume_text}
          error={errors.resume_text}
          onChange={(event) => {
            setField('resume_text', event.target.value);
          }}
        />
      </FormSection>

      <FormSection legend="Links">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            id={fieldDomId('github_url')}
            label="GitHub URL"
            type="url"
            hint="Optional. A github.com address."
            maxLength={300}
            value={values.github_url}
            error={errors.github_url}
            onChange={(event) => {
              setField('github_url', event.target.value);
            }}
          />
          <TextField
            id={fieldDomId('portfolio_url')}
            label="Portfolio URL"
            type="url"
            hint="Optional. Starts with http:// or https://."
            maxLength={300}
            value={values.portfolio_url}
            error={errors.portfolio_url}
            onChange={(event) => {
              setField('portfolio_url', event.target.value);
            }}
          />
          <TextField
            id={fieldDomId('linkedin_url')}
            label="LinkedIn URL"
            type="url"
            hint="Optional. A linkedin.com address."
            maxLength={300}
            value={values.linkedin_url}
            error={errors.linkedin_url}
            onChange={(event) => {
              setField('linkedin_url', event.target.value);
            }}
          />
        </div>
      </FormSection>

      <div className="sticky bottom-0 flex flex-wrap items-center justify-end gap-3 border-t border-ink-200 bg-ink-50 py-4">
        <p className="mr-auto text-sm text-ink-600">
          {form.isDirty ? 'You have unsaved changes.' : 'No unsaved changes.'}
        </p>
        <Button variant="secondary" onClick={handleReset} disabled={!form.isDirty || isSaving}>
          Reset changes
        </Button>
        <Button type="submit" isLoading={isSaving}>
          Save profile
        </Button>
      </div>
    </form>
  );
}
