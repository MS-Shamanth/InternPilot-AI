import type { Profile, ProfileUpdate } from '../../src/types/api';

/** Placeholder identity (security rules: no real personal data in fixtures). */
export const PROFILE_UPDATE: ProfileUpdate = {
  name: 'Demo Student',
  email: 'demo@internpilot.dev',
  location: 'Berlin, Germany',
  target_roles: ['Frontend Developer'],
  preferred_locations: ['Berlin'],
  preferred_work_modes: ['remote', 'hybrid'],
  experience_level: 'internship',
  education_level: 'bachelor',
  education: [
    {
      institution: 'Example University',
      degree: 'BSc',
      field: 'Computer Science',
      start_year: 2022,
      end_year: 2025,
    },
  ],
  technical_skills: ['React', 'TypeScript'],
  soft_skills: ['Communication'],
  projects: [
    {
      name: 'Portfolio site',
      description: 'Personal site built with React.',
      technologies: ['React'],
      url: 'https://example.com/portfolio',
    },
    {
      name: 'Task tracker',
      description: '',
      technologies: [],
      url: null,
    },
  ],
  certifications: [{ name: 'Cloud Basics', issuer: 'Example Academy', year: 2024 }],
  resume_text: 'Frontend-focused computer science student.',
  github_url: 'https://github.com/demo-student',
  portfolio_url: null,
  linkedin_url: null,
};

export const PROFILE: Profile = {
  id: 1,
  ...PROFILE_UPDATE,
  created_at: '2025-01-10T09:00:00Z',
  updated_at: '2025-01-15T09:30:00Z',
};
