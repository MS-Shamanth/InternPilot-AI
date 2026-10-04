import type { Application, ApplicationStatus } from '../../src/types/api';

interface ApplicationFixture extends Partial<Omit<Application, 'job'>> {
  title?: string;
  company?: string;
}

/** An application with its embedded job summary; `title`/`company` set the job's. */
export function makeTrackedApplication({
  title = 'Frontend Intern',
  company = 'Example Labs',
  ...overrides
}: ApplicationFixture = {}): Application {
  const id = overrides.id ?? 10;
  const jobId = overrides.job_id ?? id - 9;
  const status: ApplicationStatus = overrides.status ?? 'Applied';
  return {
    id,
    job_id: jobId,
    status,
    applied_at: '2025-01-15',
    deadline: null,
    interview_date: null,
    recruiter_name: null,
    recruiter_email: null,
    notes: '',
    outcome: null,
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-16T10:00:00Z',
    ...overrides,
    job: { id: jobId, title, company, location: 'Berlin, Germany', deadline: '2025-02-01' },
  };
}

/** One application per board column used by the tests. */
export const BOARD_APPLICATIONS: Application[] = [
  makeTrackedApplication({ id: 10, status: 'Applied', title: 'Frontend Intern' }),
  makeTrackedApplication({ id: 11, status: 'Saved', title: 'Data Intern', applied_at: null }),
  makeTrackedApplication({ id: 12, status: 'Interview', title: 'Backend Intern' }),
  makeTrackedApplication({ id: 13, status: 'Interview', title: 'QA Intern' }),
];
