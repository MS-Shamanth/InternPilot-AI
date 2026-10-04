/**
 * Display labels for backend enum values, in canonical (backend declaration) order.
 *
 * Shared by the profile form and the job list so every screen names values the same way.
 */
import type {
  ApplicationStatus,
  EducationLevel,
  EmploymentType,
  ExperienceLevel,
  JobSource,
  WorkMode,
} from '../types/api';

export interface Option<T extends string> {
  value: T;
  label: string;
}

export const WORK_MODE_OPTIONS: readonly Option<WorkMode>[] = [
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'Onsite' },
];

export const EXPERIENCE_LEVEL_OPTIONS: readonly Option<ExperienceLevel>[] = [
  { value: 'internship', label: 'Internship' },
  { value: 'entry', label: 'Entry level' },
  { value: 'junior', label: 'Junior' },
  { value: 'mid', label: 'Mid level' },
  { value: 'senior', label: 'Senior' },
];

export const EDUCATION_LEVEL_OPTIONS: readonly Option<EducationLevel>[] = [
  { value: 'high_school', label: 'High school' },
  { value: 'diploma', label: 'Diploma' },
  { value: 'bachelor', label: "Bachelor's" },
  { value: 'master', label: "Master's" },
  { value: 'phd', label: 'PhD' },
];

export const EMPLOYMENT_TYPE_OPTIONS: readonly Option<EmploymentType>[] = [
  { value: 'internship', label: 'Internship' },
  { value: 'full_time', label: 'Full-time' },
  { value: 'part_time', label: 'Part-time' },
  { value: 'contract', label: 'Contract' },
];

export const JOB_SOURCE_OPTIONS: readonly Option<JobSource>[] = [
  { value: 'seed', label: 'Demo data' },
  { value: 'fixture', label: 'Local fixtures' },
  { value: 'remotive', label: 'Remotive' },
  { value: 'arbeitnow', label: 'Arbeitnow' },
  { value: 'payload', label: 'Imported payload' },
];

/**
 * The status enum values, used only to validate `?status=` before `/applications/meta` loads.
 * Column order and allowed moves always come from the meta endpoint.
 */
export const APPLICATION_STATUSES: readonly ApplicationStatus[] = [
  'Saved',
  'Interested',
  'Applied',
  'Assessment',
  'Interview',
  'Rejected',
  'Offer',
  'Withdrawn',
];

export function isApplicationStatus(value: string): value is ApplicationStatus {
  return (APPLICATION_STATUSES as readonly string[]).includes(value);
}

/** The label of `value`, or the raw value when it is not one of `options`. */
export function optionLabel<T extends string>(options: readonly Option<T>[], value: T): string {
  return options.find((option) => option.value === value)?.label ?? value;
}

/** Type guard: `value` is one of the option values. */
export function isOptionValue<T extends string>(
  options: readonly Option<T>[],
  value: string,
): value is T {
  return options.some((option) => option.value === value);
}
