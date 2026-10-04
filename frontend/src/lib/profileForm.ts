/**
 * Profile form values and their mapping to and from the API (R1.1, design.md §8.1).
 *
 * The form keeps text inputs as strings (years included) and gives list items a client-side
 * `key`; `formValuesToUpdate` produces the full `PUT /profile` body. No normalization or
 * validation happens here: the backend owns both.
 */
import type {
  Certification,
  EducationEntry,
  EducationLevel,
  ExperienceLevel,
  Profile,
  ProfileUpdate,
  Project,
  WorkMode,
} from '../types/api';
import {
  EDUCATION_LEVEL_OPTIONS,
  EXPERIENCE_LEVEL_OPTIONS,
  WORK_MODE_OPTIONS,
} from './enumOptions';
import type { Option } from './enumOptions';

export interface EducationFormValues {
  key: string;
  institution: string;
  degree: string;
  field: string;
  start_year: string;
  end_year: string;
}

export interface ProjectFormValues {
  key: string;
  name: string;
  description: string;
  technologies: string[];
  url: string;
}

export interface CertificationFormValues {
  key: string;
  name: string;
  issuer: string;
  year: string;
}

export interface ProfileFormValues {
  name: string;
  email: string;
  location: string;
  target_roles: string[];
  preferred_locations: string[];
  preferred_work_modes: WorkMode[];
  experience_level: ExperienceLevel | '';
  education_level: EducationLevel | '';
  education: EducationFormValues[];
  technical_skills: string[];
  soft_skills: string[];
  projects: ProjectFormValues[];
  certifications: CertificationFormValues[];
  resume_text: string;
  github_url: string;
  portfolio_url: string;
  linkedin_url: string;
}

export { EDUCATION_LEVEL_OPTIONS, EXPERIENCE_LEVEL_OPTIONS, WORK_MODE_OPTIONS };

/** The option whose value equals `value`, or `''` ("Not specified") for anything else. */
export function parseOption<T extends string>(
  options: readonly Option<T>[],
  value: string,
): T | '' {
  return options.find((option) => option.value === value)?.value ?? '';
}

/** Selected work modes in canonical option order, so the payload does not depend on clicks. */
export function toggleWorkMode(
  selected: readonly WorkMode[],
  mode: WorkMode,
  checked: boolean,
): WorkMode[] {
  return WORK_MODE_OPTIONS.map((option) => option.value).filter((value) =>
    value === mode ? checked : selected.includes(value),
  );
}

export function replaceAt<T>(items: readonly T[], index: number, item: T): T[] {
  return items.map((existing, position) => (position === index ? item : existing));
}

export function removeAt<T>(items: readonly T[], index: number): T[] {
  return items.filter((_, position) => position !== index);
}

function text(value: string | null): string {
  return value ?? '';
}

function yearText(value: number | null): string {
  return value === null ? '' : String(value);
}

function nullable(value: string): string | null {
  return value === '' ? null : value;
}

function yearValue(value: string): number | null {
  if (value.trim() === '') {
    return null;
  }
  const year = Number(value);
  return Number.isNaN(year) ? null : year;
}

export function emptyEducation(key: string): EducationFormValues {
  return { key, institution: '', degree: '', field: '', start_year: '', end_year: '' };
}

export function emptyProject(key: string): ProjectFormValues {
  return { key, name: '', description: '', technologies: [], url: '' };
}

export function emptyCertification(key: string): CertificationFormValues {
  return { key, name: '', issuer: '', year: '' };
}

/** Form values for a stored profile; list items get keys `stored-<index>`. */
export function profileToFormValues(profile: Profile): ProfileFormValues {
  return {
    name: profile.name,
    email: profile.email,
    location: text(profile.location),
    target_roles: [...profile.target_roles],
    preferred_locations: [...profile.preferred_locations],
    preferred_work_modes: [...profile.preferred_work_modes],
    experience_level: profile.experience_level ?? '',
    education_level: profile.education_level ?? '',
    education: profile.education.map((entry, index) => ({
      key: `stored-${String(index)}`,
      institution: entry.institution,
      degree: text(entry.degree),
      field: text(entry.field),
      start_year: yearText(entry.start_year),
      end_year: yearText(entry.end_year),
    })),
    technical_skills: [...profile.technical_skills],
    soft_skills: [...profile.soft_skills],
    projects: profile.projects.map((project, index) => ({
      key: `stored-${String(index)}`,
      name: project.name,
      description: project.description,
      technologies: [...project.technologies],
      url: text(project.url),
    })),
    certifications: profile.certifications.map((certification, index) => ({
      key: `stored-${String(index)}`,
      name: certification.name,
      issuer: text(certification.issuer),
      year: yearText(certification.year),
    })),
    resume_text: profile.resume_text,
    github_url: text(profile.github_url),
    portfolio_url: text(profile.portfolio_url),
    linkedin_url: text(profile.linkedin_url),
  };
}

function toEducation(entry: EducationFormValues): EducationEntry {
  return {
    institution: entry.institution,
    degree: nullable(entry.degree),
    field: nullable(entry.field),
    start_year: yearValue(entry.start_year),
    end_year: yearValue(entry.end_year),
  };
}

function toProject(project: ProjectFormValues): Project {
  return {
    name: project.name,
    description: project.description,
    technologies: [...project.technologies],
    url: nullable(project.url),
  };
}

function toCertification(certification: CertificationFormValues): Certification {
  return {
    name: certification.name,
    issuer: nullable(certification.issuer),
    year: yearValue(certification.year),
  };
}

/** The full `PUT /profile` body: every field, with empty optional inputs sent as `null`. */
export function formValuesToUpdate(values: ProfileFormValues): ProfileUpdate {
  return {
    name: values.name,
    email: values.email,
    location: nullable(values.location),
    target_roles: [...values.target_roles],
    preferred_locations: [...values.preferred_locations],
    preferred_work_modes: [...values.preferred_work_modes],
    experience_level: values.experience_level === '' ? null : values.experience_level,
    education_level: values.education_level === '' ? null : values.education_level,
    education: values.education.map(toEducation),
    technical_skills: [...values.technical_skills],
    soft_skills: [...values.soft_skills],
    projects: values.projects.map(toProject),
    certifications: values.certifications.map(toCertification),
    resume_text: values.resume_text,
    github_url: nullable(values.github_url),
    portfolio_url: nullable(values.portfolio_url),
    linkedin_url: nullable(values.linkedin_url),
  };
}

const FIELD_LABELS: Readonly<Record<string, string>> = {
  name: 'Name',
  email: 'Email',
  location: 'Location',
  target_roles: 'Target roles',
  preferred_locations: 'Preferred locations',
  preferred_work_modes: 'Preferred work modes',
  experience_level: 'Experience level',
  education_level: 'Education level',
  education: 'Education',
  technical_skills: 'Technical skills',
  soft_skills: 'Soft skills',
  projects: 'Projects',
  certifications: 'Certifications',
  resume_text: 'Resume text',
  github_url: 'GitHub URL',
  portfolio_url: 'Portfolio URL',
  linkedin_url: 'LinkedIn URL',
};

const ITEM_LABELS: Readonly<Record<string, string>> = {
  target_roles: 'Target role',
  preferred_locations: 'Preferred location',
  technical_skills: 'Technical skill',
  soft_skills: 'Soft skill',
  education: 'Education',
  projects: 'Project',
  certifications: 'Certification',
  technologies: 'Technology',
};

const NESTED_LABELS: Readonly<Record<string, string>> = {
  institution: 'Institution',
  degree: 'Degree',
  field: 'Field of study',
  start_year: 'Start year',
  end_year: 'End year',
  name: 'Name',
  description: 'Description',
  technologies: 'Technologies',
  url: 'URL',
  issuer: 'Issuer',
  year: 'Year',
};

const SEGMENT = /([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]/g;

/**
 * Human label for a field path, for the error summary:
 * `projects[1].url` → "Project 2 · URL"; `technical_skills[0]` → "Technical skill 1".
 */
export function profileFieldLabel(path: string): string {
  if (path === '') {
    return 'Profile';
  }
  const parts: string[] = [];
  const fieldLabel = (name: string): string =>
    (parts.length === 0 ? FIELD_LABELS[name] : NESTED_LABELS[name]) ?? name;
  let pendingName: string | null = null;
  for (const match of path.matchAll(SEGMENT)) {
    const [, name, index] = match;
    if (name !== undefined) {
      if (pendingName !== null) {
        parts.push(fieldLabel(pendingName));
      }
      pendingName = name;
    } else if (index !== undefined && pendingName !== null) {
      const itemLabel = ITEM_LABELS[pendingName] ?? pendingName;
      parts.push(`${itemLabel} ${String(Number(index) + 1)}`);
      pendingName = null;
    }
  }
  if (pendingName !== null) {
    parts.push(fieldLabel(pendingName));
  }
  return parts.join(' · ');
}
