import type {
  Application,
  ApplicationsMeta,
  JobDetail,
  JobSummary,
  MatchExplanation,
  Page,
} from '../../src/types/api';

/** The backend's transition table (design.md §6). */
export const APPLICATIONS_META: ApplicationsMeta = {
  statuses: [
    'Saved',
    'Interested',
    'Applied',
    'Assessment',
    'Interview',
    'Rejected',
    'Offer',
    'Withdrawn',
  ],
  transitions: {
    Saved: ['Interested', 'Applied', 'Withdrawn'],
    Interested: ['Saved', 'Applied', 'Withdrawn'],
    Applied: ['Assessment', 'Interview', 'Rejected', 'Offer', 'Withdrawn'],
    Assessment: ['Interview', 'Rejected', 'Offer', 'Withdrawn'],
    Interview: ['Assessment', 'Rejected', 'Offer', 'Withdrawn'],
    Rejected: ['Interested'],
    Offer: ['Withdrawn'],
    Withdrawn: ['Interested'],
  },
};

export function makeJob(overrides: Partial<JobSummary> = {}): JobSummary {
  return {
    id: 1,
    title: 'Frontend Intern',
    company: 'Example Labs',
    location: 'Berlin, Germany',
    employment_type: 'internship',
    work_mode: 'hybrid',
    experience_level: 'internship',
    salary_min: 1500,
    salary_max: 2000,
    salary_currency: 'EUR',
    salary_period: 'month',
    deadline: '2025-02-01',
    source: 'seed',
    discovered_at: '2025-01-10T09:00:00Z',
    required_skills: ['React', 'TypeScript'],
    preferred_skills: ['Testing Library'],
    match_score: 0,
    is_bookmarked: false,
    is_hidden: false,
    application_status: null,
    ...overrides,
  };
}

export function makePage(
  items: JobSummary[],
  overrides: Partial<Page<JobSummary>> = {},
): Page<JobSummary> {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    total_pages: items.length === 0 ? 0 : 1,
    ...overrides,
  };
}

export function makeApplication(job: JobSummary): Application {
  return {
    id: 10,
    job_id: job.id,
    status: 'Applied',
    applied_at: '2025-01-15',
    deadline: null,
    interview_date: null,
    recruiter_name: null,
    recruiter_email: null,
    notes: '',
    outcome: null,
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-15T10:00:00Z',
    job: {
      id: job.id,
      title: job.title,
      company: job.company,
      location: job.location,
      deadline: job.deadline,
    },
  };
}

/** A backend match explanation for job 1 scoring 72. */
export function makeMatchExplanation(overrides: Partial<MatchExplanation> = {}): MatchExplanation {
  return {
    job_id: 1,
    score: 72,
    algorithm_version: 'v1',
    factors: [
      {
        key: 'required_skills',
        label: 'Required skills',
        weight: 35,
        points: 17.5,
        ratio: 0.5,
        detail: '1 of 2 required skills',
      },
      {
        key: 'preferred_skills',
        label: 'Preferred skills',
        weight: 10,
        points: 10,
        ratio: 1,
        detail: '1 of 1 preferred skills',
      },
    ],
    matched_required_skills: ['React'],
    missing_required_skills: ['TypeScript'],
    matched_preferred_skills: ['Testing Library'],
    missing_preferred_skills: [],
    positive_reasons: ['You have 1 of 2 required skills: React'],
    negative_reasons: ['Missing required skills: TypeScript'],
    ...overrides,
  };
}

/** A job detail as the backend sends it (design.md §8.3). */
export function makeJobDetail(overrides: Partial<JobDetail> = {}): JobDetail {
  return {
    ...makeJob({ match_score: 72 }),
    description: 'Build accessible UI.\n\nWork with the design team.',
    application_url: 'https://jobs.example.com/frontend-intern',
    min_education_level: 'bachelor',
    match_explanation: makeMatchExplanation(),
    application: null,
    ...overrides,
  };
}
