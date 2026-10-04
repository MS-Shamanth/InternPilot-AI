import type { JobSummary } from '../../types/api';
import { Select } from '../ui/Select';

interface JobPickerProps {
  jobs: readonly JobSummary[];
  /** The selected job id, or `null` for none. */
  value: number | null;
  onChange: (jobId: number | null) => void;
  disabled?: boolean;
  hint?: string;
}

/** Labelled job `<select>`; options show title, company and the backend's match score. */
export function JobPicker({ jobs, value, onChange, disabled = false, hint }: JobPickerProps) {
  return (
    <Select
      label="Job"
      hint={hint}
      value={value === null ? '' : String(value)}
      disabled={disabled}
      onChange={(event) => {
        onChange(event.target.value === '' ? null : Number(event.target.value));
      }}
    >
      <option value="">Choose a job…</option>
      {jobs.map((job) => (
        <option key={job.id} value={job.id}>
          {`${job.title} · ${job.company} (match ${String(job.match_score)}/100)`}
        </option>
      ))}
    </Select>
  );
}
