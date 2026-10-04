import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api/client';
import { getProfile, updateProfile } from '../../src/api/profile';
import { ToastProvider } from '../../src/components/ui/toast/ToastProvider';
import ProfilePage from '../../src/pages/ProfilePage';
import type { Profile, ProfileUpdate } from '../../src/types/api';
import { createTestQueryClient } from '../hooks/queryTestUtils';
import { PROFILE, PROFILE_UPDATE } from './profileFixtures';

vi.mock('../../src/api/profile');

const getProfileMock = vi.mocked(getProfile);
const updateProfileMock = vi.mocked(updateProfile);

function renderPage() {
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <ToastProvider>
        <ProfilePage />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { user };
}

async function findForm(): Promise<HTMLElement> {
  return screen.findByRole('form', { name: 'Profile' });
}

function group(name: string): HTMLElement {
  return screen.getByRole('group', { name });
}

/** Item names of a string list editor, read from its Remove buttons. */
function chipNames(list: HTMLElement): string[] {
  return within(list)
    .getAllByRole('button', { name: /^Remove / })
    .map((button) => (button.getAttribute('aria-label') ?? '').replace(/^Remove /, ''));
}

beforeEach(() => {
  getProfileMock.mockResolvedValue(PROFILE);
});

describe('ProfilePage', () => {
  it('shows a loading skeleton and then the form populated from the profile', async () => {
    renderPage();

    expect(screen.getByRole('status', { busy: true })).toHaveTextContent('Loading profile…');
    await findForm();

    expect(screen.getByLabelText(/^Name/)).toHaveValue('Demo Student');
    expect(screen.getByLabelText(/^Email/)).toHaveValue('demo@internpilot.dev');
    expect(screen.getByLabelText(/^Location/)).toHaveValue('Berlin, Germany');
    expect(screen.getByRole('checkbox', { name: 'Remote' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Onsite' })).not.toBeChecked();
    expect(screen.getByLabelText('Experience level')).toHaveValue('internship');
    expect(screen.getByLabelText(/^Education level/)).toHaveValue('bachelor');
    expect(within(group('Technical skills')).getByText('TypeScript')).toBeInTheDocument();
    expect(within(group('Education 1')).getByLabelText(/^Institution/)).toHaveValue(
      'Example University',
    );
    expect(within(group('Project 2')).getByLabelText(/^Project name/)).toHaveValue('Task tracker');
    expect(within(group('Certification 1')).getByLabelText('Year')).toHaveValue(2024);
    expect(screen.getByLabelText(/^GitHub URL/)).toHaveValue('https://github.com/demo-student');
  });

  it('sends the full profile on save, toasts and resets to the stored profile', async () => {
    const saved: Profile = {
      ...PROFILE,
      name: 'Demo Graduate',
      experience_level: 'junior',
      technical_skills: ['Python', 'React', 'TypeScript'],
      updated_at: '2025-01-16T10:00:00Z',
    };
    updateProfileMock.mockResolvedValue(saved);
    const { user } = renderPage();
    await findForm();

    const name = screen.getByLabelText(/^Name/);
    await user.clear(name);
    await user.type(name, 'Demo Graduate');
    await user.selectOptions(screen.getByLabelText('Experience level'), 'junior');
    await user.type(screen.getByLabelText(/^Add technical skill/), 'Python');
    await user.click(screen.getByRole('button', { name: 'Add technical skill' }));
    expect(screen.getByText('You have unsaved changes.')).toBeInTheDocument();
    getProfileMock.mockResolvedValue(saved);
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    expect(await screen.findByText('Profile saved')).toBeInTheDocument();
    const expected: ProfileUpdate = {
      ...PROFILE_UPDATE,
      name: 'Demo Graduate',
      experience_level: 'junior',
      technical_skills: ['React', 'TypeScript', 'Python'],
    };
    expect(updateProfileMock).toHaveBeenCalledTimes(1);
    expect(updateProfileMock.mock.calls[0]?.[0]).toEqual(expected);
    expect(chipNames(group('Technical skills'))).toEqual(['Python', 'React', 'TypeScript']);
    expect(screen.getByText('No unsaved changes.')).toBeInTheDocument();
  });

  it('adds a skill with Enter and removes one with the keyboard without submitting', async () => {
    const { user } = renderPage();
    await findForm();
    const skills = group('Technical skills');
    const input = within(skills).getByLabelText(/^Add technical skill/);

    await user.click(input);
    await user.keyboard('Vue{Enter}');
    expect(within(skills).getByRole('button', { name: 'Remove Vue' })).toBeInTheDocument();
    expect(input).toHaveValue('');

    within(skills).getByRole('button', { name: 'Remove React' }).focus();
    await user.keyboard('{Enter}');

    expect(within(skills).queryByRole('button', { name: 'Remove React' })).not.toBeInTheDocument();
    expect(chipNames(skills)).toEqual(['TypeScript', 'Vue']);
    expect(input).toHaveFocus();
    expect(updateProfileMock).not.toHaveBeenCalled();
  });

  it('shows 422 errors next to their fields and in a focused summary', async () => {
    updateProfileMock.mockRejectedValue(
      new ApiError('VALIDATION_ERROR', 'The request is invalid.', 422, [
        {
          loc: ['body', 'name'],
          msg: 'String should have at least 1 character',
          type: 'too_short',
        },
        {
          loc: ['body', 'technical_skills', 1],
          msg: 'Value error, Skill must contain at least one letter, digit or symbol',
          type: 'value_error',
        },
        {
          loc: ['body', 'projects', 1, 'url'],
          msg: 'URL must use http or https',
          type: 'value_error',
        },
      ]),
    );
    const { user } = renderPage();
    await findForm();

    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    const summary = await screen.findByRole('alert', {
      name: 'There are 3 problems with your profile',
    });
    await waitFor(() => {
      expect(summary).toHaveFocus();
    });
    const projectUrl = within(group('Project 2')).getByLabelText(/^Project URL/);
    expect(projectUrl).toHaveAttribute('aria-invalid', 'true');
    expect(projectUrl).toHaveAccessibleDescription(
      expect.stringContaining('Error: URL must use http or https'),
    );
    expect(within(group('Project 1')).getByLabelText(/^Project URL/)).not.toHaveAttribute(
      'aria-invalid',
    );
    expect(screen.getByLabelText(/^Name/)).toHaveAccessibleDescription(
      'Error: String should have at least 1 character',
    );
    expect(
      within(group('Technical skills')).getByRole('button', { name: 'Remove TypeScript' }),
    ).toHaveAccessibleDescription('Error: Skill must contain at least one letter, digit or symbol');
    expect(screen.getByText('The request is invalid.')).toBeInTheDocument();

    await user.click(
      within(summary).getByRole('link', { name: 'Project 2 · URL: URL must use http or https' }),
    );
    expect(projectUrl).toHaveFocus();
  });

  it('shows the envelope message on the email field when the email is taken', async () => {
    updateProfileMock.mockRejectedValue(
      new ApiError('EMAIL_TAKEN', 'That email is already in use.', 409),
    );
    const { user } = renderPage();
    await findForm();

    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    const email = screen.getByLabelText(/^Email/);
    await waitFor(() => {
      expect(email).toHaveAccessibleDescription('Error: That email is already in use.');
    });
    expect(
      screen.getAllByText('That email is already in use.', { exact: false }).length,
    ).toBeGreaterThan(1);
  });

  it('shows an error state and refetches when Retry is pressed', async () => {
    getProfileMock.mockRejectedValueOnce(new ApiError('NOT_FOUND', 'Profile not found.', 404));
    const { user } = renderPage();

    expect(await screen.findByText('Could not load your profile')).toBeInTheDocument();
    expect(screen.getByText('Profile not found.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    await findForm();
    expect(getProfileMock).toHaveBeenCalledTimes(2);
  });
});
