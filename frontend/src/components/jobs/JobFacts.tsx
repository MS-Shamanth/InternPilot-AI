import type { ReactNode } from 'react';
import {
  EDUCATION_LEVEL_OPTIONS,
  EMPLOYMENT_TYPE_OPTIONS,
  EXPERIENCE_LEVEL_OPTIONS,
  JOB_SOURCE_OPTIONS,
  WORK_MODE_OPTIONS,
  optionLabel,
} from '../../lib/enumOptions';
import { formatDateTime, formatSalary } from '../../lib/format';
import type { IsoDate, JobDetail } from '../../types/api';
import { DeadlineText } from './DeadlineText';

const NOT_SPECIFIED = 'Not specified';

interface JobFactsProps {
  job: JobDetail;
  /** The viewer's local date, `YYYY-MM-DD`, for the days-left text. */
  today: IsoDate;
}

interface Fact {
  label: string;
  value: ReactNode;
}

/** Every structured fact of a job as a labelled description list (R2.1). */
export function JobFacts({ job, today }: JobFactsProps) {
  const facts: Fact[] = [
    { label: 'Work mode', value: optionLabel(WORK_MODE_OPTIONS, job.work_mode) },
    { label: 'Employment type', value: optionLabel(EMPLOYMENT_TYPE_OPTIONS, job.employment_type) },
    {
      label: 'Experience level',
      value:
        job.experience_level === null
          ? NOT_SPECIFIED
          : optionLabel(EXPERIENCE_LEVEL_OPTIONS, job.experience_level),
    },
    {
      label: 'Minimum education',
      value:
        job.min_education_level === null
          ? NOT_SPECIFIED
          : optionLabel(EDUCATION_LEVEL_OPTIONS, job.min_education_level),
    },
    { label: 'Salary', value: formatSalary(job) },
    {
      label: 'Deadline',
      value: <DeadlineText deadline={job.deadline} today={today} prefix="" />,
    },
    { label: 'Source', value: optionLabel(JOB_SOURCE_OPTIONS, job.source) },
    {
      label: 'Discovered',
      value: <time dateTime={job.discovered_at}>{formatDateTime(job.discovered_at)}</time>,
    },
  ];

  return (
    <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
      {facts.map(({ label, value }) => (
        <div key={label}>
          <dt className="font-medium text-ink-600">{label}</dt>
          <dd className="text-ink-900">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
