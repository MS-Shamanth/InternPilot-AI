import { describe, expect, it } from 'vitest';
import {
  formValuesToUpdate,
  profileFieldLabel,
  profileToFormValues,
  toggleWorkMode,
} from '../../src/lib/profileForm';
import { PROFILE, PROFILE_UPDATE } from '../profile/profileFixtures';

describe('profileToFormValues / formValuesToUpdate', () => {
  it('round-trips a stored profile into the same full update payload', () => {
    expect(formValuesToUpdate(profileToFormValues(PROFILE))).toEqual(PROFILE_UPDATE);
  });

  it('sends empty optional inputs as null and years as numbers', () => {
    const values = profileToFormValues(PROFILE);
    const update = formValuesToUpdate({
      ...values,
      location: '',
      github_url: '',
      experience_level: '',
      education: [
        {
          key: 'k',
          institution: 'TU Berlin',
          degree: '',
          field: '',
          start_year: '2021',
          end_year: '',
        },
      ],
    });
    expect(update.location).toBeNull();
    expect(update.github_url).toBeNull();
    expect(update.experience_level).toBeNull();
    expect(update.education).toEqual([
      { institution: 'TU Berlin', degree: null, field: null, start_year: 2021, end_year: null },
    ]);
  });
});

describe('toggleWorkMode', () => {
  it('keeps the canonical order when modes are toggled in any order', () => {
    expect(toggleWorkMode(['onsite'], 'remote', true)).toEqual(['remote', 'onsite']);
    expect(toggleWorkMode(['remote', 'onsite'], 'remote', false)).toEqual(['onsite']);
  });
});

describe('profileFieldLabel', () => {
  it('names top-level, list-item and nested fields for the error summary', () => {
    expect(profileFieldLabel('github_url')).toBe('GitHub URL');
    expect(profileFieldLabel('technical_skills[0]')).toBe('Technical skill 1');
    expect(profileFieldLabel('projects[1].url')).toBe('Project 2 · URL');
    expect(profileFieldLabel('projects[0].technologies[2]')).toBe('Project 1 · Technology 3');
    expect(profileFieldLabel('')).toBe('Profile');
  });
});
