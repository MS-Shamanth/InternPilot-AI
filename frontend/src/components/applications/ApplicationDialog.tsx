import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import {
  applicationFieldErrors,
  applicationToFormValues,
  buildCreateBody,
  buildUpdatePatch,
  emptyApplicationForm,
  isEmptyPatch,
} from '../../lib/applicationForm';
import type { ApplicationFormField, ApplicationFormValues } from '../../lib/applicationForm';
import { NO_FIELD_ERRORS, clearFieldErrors, fieldDomId } from '../../lib/validationErrors';
import type { FieldErrors } from '../../lib/validationErrors';
import type {
  Application,
  ApplicationCreate,
  ApplicationStatus,
  ApplicationUpdate,
  JobSummary,
} from '../../types/api';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { ErrorState } from '../ui/ErrorState';
import { Select } from '../ui/Select';
import { TextArea } from '../ui/TextArea';
import { TextField } from '../ui/TextField';

const FIELD_LABELS: Record<ApplicationFormField, string> = {
  job_id: 'Job',
  status: 'Status',
  notes: 'Notes',
  applied_at: 'Applied on',
  deadline: 'Application deadline',
  interview_date: 'Interview',
  recruiter_name: 'Recruiter name',
  recruiter_email: 'Recruiter email',
  outcome: 'Outcome',
};

const EDIT_FIELDS: readonly ApplicationFormField[] = [
  'notes',
  'applied_at',
  'deadline',
  'interview_date',
  'recruiter_name',
  'recruiter_email',
  'outcome',
];
const CREATE_FIELDS: readonly ApplicationFormField[] = ['job_id', 'status', ...EDIT_FIELDS];

/** Jobs offered when creating; tracked jobs are left out because each job has one application. */
export interface JobPicker {
  jobs: readonly JobSummary[] | undefined;
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
  /** Total jobs when more exist than were loaded, else `null`. */
  truncatedTotal: number | null;
}

interface CreateModeProps {
  mode: 'create';
  /** Statuses in canonical order (any status may be used on create). */
  statuses: readonly ApplicationStatus[];
  jobPicker: JobPicker;
  onSubmit: (body: ApplicationCreate) => Promise<unknown>;
}

interface EditModeProps {
  mode: 'edit';
  application: Application;
  onSubmit: (patch: ApplicationUpdate) => Promise<unknown>;
  /** The user saved without changing anything; no request is made. */
  onNoChanges: () => void;
}

type ApplicationDialogProps = (CreateModeProps | EditModeProps) & {
  open: boolean;
  onClose: () => void;
  isSaving: boolean;
};

function timeZoneName(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function JobSelectOptions({ jobs }: { jobs: readonly JobSummary[] }) {
  const untracked = jobs.filter((job) => job.application_status === null);
  return (
    <>
      <option value="">Choose a job</option>
      {untracked.map((job) => (
        <option key={job.id} value={String(job.id)}>
          {job.title} · {job.company}
        </option>
      ))}
    </>
  );
}

/**
 * Create or edit an application's details (R5.1, R5.7). Edits send only changed fields, with
 * `null` for cleared ones; status changes use the Move controls instead. Server validation
 * errors appear next to their fields.
 */
export function ApplicationDialog(props: ApplicationDialogProps) {
  const { open, onClose, isSaving } = props;
  const formId = useId();
  const firstFieldRef = useRef<HTMLSelectElement>(null);
  const firstEditFieldRef = useRef<HTMLInputElement>(null);
  const focusErrorRef = useRef(false);
  const [values, setValues] = useState<ApplicationFormValues>(() =>
    props.mode === 'edit' ? applicationToFormValues(props.application) : emptyApplicationForm(),
  );
  const [errors, setErrors] = useState<FieldErrors>(NO_FIELD_ERRORS);

  useEffect(() => {
    if (!focusErrorRef.current) {
      return;
    }
    focusErrorRef.current = false;
    const first = Object.keys(errors)[0];
    if (first !== undefined) {
      document.getElementById(fieldDomId(first))?.focus();
    }
  }, [errors]);

  const shownFields = props.mode === 'create' ? CREATE_FIELDS : EDIT_FIELDS;
  const otherErrors = Object.entries(errors).filter(
    ([path]) => !shownFields.some((field) => field === path),
  );

  function showErrors(next: FieldErrors) {
    focusErrorRef.current = true;
    setErrors(next);
  }

  function update(field: Exclude<ApplicationFormField, 'status'>, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => clearFieldErrors(current, field));
  }

  async function run(request: () => Promise<unknown>) {
    try {
      await request();
    } catch (error) {
      showErrors(applicationFieldErrors(error));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (props.mode === 'create') {
      if (values.job_id === '') {
        showErrors({ job_id: 'Choose a job to track.' });
        return;
      }
      await run(() => props.onSubmit(buildCreateBody(values)));
      return;
    }
    const patch = buildUpdatePatch(props.application, values);
    if (isEmptyPatch(patch)) {
      props.onNoChanges();
      return;
    }
    await run(() => props.onSubmit(patch));
  }

  function textField(
    field: Exclude<ApplicationFormField, 'job_id' | 'status' | 'notes'>,
    type: 'text' | 'email' | 'date' | 'datetime-local',
    options: { hint?: string; maxLength?: number } = {},
  ) {
    return (
      <TextField
        ref={field === 'applied_at' ? firstEditFieldRef : undefined}
        id={fieldDomId(field)}
        label={FIELD_LABELS[field]}
        type={type}
        value={values[field]}
        error={errors[field]}
        hint={options.hint}
        maxLength={options.maxLength}
        onChange={(event) => {
          update(field, event.target.value);
        }}
      />
    );
  }

  function jobHint(picker: JobPicker): string | undefined {
    if (picker.isLoading) {
      return 'Loading jobs…';
    }
    if (picker.jobs === undefined) {
      return undefined;
    }
    return picker.truncatedTotal === null
      ? 'Jobs you already track are not listed.'
      : `Showing the first ${String(picker.jobs.length)} of ${String(picker.truncatedTotal)} jobs by title; jobs you already track are not listed. To track another job, use “Save to tracker” on its page.`;
  }

  function renderJobPicker(picker: JobPicker) {
    // The select is always rendered so it can take focus when the dialog opens.
    const failed = !picker.isLoading && picker.jobs === undefined;
    return (
      <>
        <Select
          ref={firstFieldRef}
          id={fieldDomId('job_id')}
          label={FIELD_LABELS.job_id}
          required
          hint={jobHint(picker)}
          aria-busy={picker.isLoading || undefined}
          value={values.job_id}
          error={errors.job_id}
          onChange={(event) => {
            update('job_id', event.target.value);
          }}
        >
          {picker.jobs === undefined ? (
            <option value="">
              {picker.isLoading ? 'Loading jobs…' : 'Jobs could not be loaded'}
            </option>
          ) : (
            <JobSelectOptions jobs={picker.jobs} />
          )}
        </Select>
        {failed && (
          <ErrorState title="Could not load jobs" error={picker.error} onRetry={picker.onRetry} />
        )}
      </>
    );
  }

  const isCreate = props.mode === 'create';
  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      closeOnBackdropClick={false}
      title={isCreate ? 'Add application' : 'Edit application'}
      description={
        props.mode === 'create'
          ? 'Track a job and record what you know so far.'
          : `${props.application.job.title} · ${props.application.job.company}`
      }
      initialFocusRef={isCreate ? firstFieldRef : firstEditFieldRef}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form={formId} isLoading={isSaving}>
            {isCreate ? 'Add application' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form
        id={formId}
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
      >
        {otherErrors.length > 0 && (
          <div role="alert" className="rounded border border-danger-700 bg-danger-50 p-3 text-sm">
            <ul className="list-disc pl-5 text-danger-800">
              {otherErrors.map(([path, message]) => (
                <li key={path}>{message}</li>
              ))}
            </ul>
          </div>
        )}
        {props.mode === 'create' && (
          <>
            {renderJobPicker(props.jobPicker)}
            <Select
              id={fieldDomId('status')}
              label={FIELD_LABELS.status}
              hint="Later changes use “Move to…” so only allowed moves are offered."
              value={values.status}
              error={errors.status}
              onChange={(event) => {
                const status = props.statuses.find((value) => value === event.target.value);
                if (status !== undefined) {
                  setValues((current) => ({ ...current, status }));
                  setErrors((current) => clearFieldErrors(current, 'status'));
                }
              }}
            >
              {props.statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </Select>
          </>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          {textField('applied_at', 'date')}
          {textField('deadline', 'date')}
          {textField('interview_date', 'datetime-local', {
            hint: `Your local time (${timeZoneName()}).`,
          })}
          {textField('outcome', 'text', { maxLength: 500 })}
          {textField('recruiter_name', 'text', { maxLength: 120 })}
          {textField('recruiter_email', 'email', { maxLength: 254 })}
        </div>
        <TextArea
          id={fieldDomId('notes')}
          label={FIELD_LABELS.notes}
          value={values.notes}
          error={errors.notes}
          maxLength={5000}
          onChange={(event) => {
            update('notes', event.target.value);
          }}
        />
      </form>
    </Dialog>
  );
}
