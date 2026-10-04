import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '../../src/AppProviders';
import {
  getApplicationsMeta,
  listApplications,
  updateApplication,
} from '../../src/api/applications';
import { ApiError } from '../../src/api/client';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';
import ApplicationsPage from '../../src/pages/ApplicationsPage';
import { APPLICATIONS_META } from '../jobs/jobFixtures';
import { BOARD_APPLICATIONS } from './applicationFixtures';

vi.mock('../../src/api/applications');
vi.mock('../../src/api/jobs');

const updateMock = vi.mocked(updateApplication);

function renderBoard() {
  render(
    <MemoryRouter initialEntries={['/applications?view=board']} future={ROUTER_FUTURE_FLAGS}>
      <AppProviders>
        <ApplicationsPage />
      </AppProviders>
    </MemoryRouter>,
  );
  return { user: userEvent.setup() };
}

function column(status: string): HTMLElement {
  return screen.getByRole('region', { name: new RegExp(`^${status}\\b`) });
}

function card(title: string): HTMLElement {
  const heading = screen.getByRole('heading', { level: 3, name: title });
  const article = heading.closest('article');
  if (article === null) {
    throw new Error(`No card for ${title}`);
  }
  return article;
}

function moveButton(title: string): HTMLElement {
  return within(card(title)).getByRole('button', { name: /^Move to…/ });
}

function menuItemNames(): string[] {
  return within(screen.getByRole('menu'))
    .getAllByRole('menuitem')
    .map((item) => item.textContent ?? '');
}

/** A minimal `DataTransfer` stand-in (jsdom has none). */
function createDataTransfer() {
  const data = new Map<string, string>();
  return {
    dropEffect: 'none',
    effectAllowed: 'all',
    setData: (type: string, value: string) => {
      data.set(type, value);
    },
    getData: (type: string) => data.get(type) ?? '',
  };
}

async function findBoard() {
  await screen.findByRole('heading', { level: 3, name: 'Frontend Intern' });
}

beforeEach(() => {
  vi.mocked(getApplicationsMeta).mockResolvedValue(APPLICATIONS_META);
  vi.mocked(listApplications).mockResolvedValue(BOARD_APPLICATIONS);
  updateMock.mockImplementation((id, changes) => {
    const original = BOARD_APPLICATIONS.find((application) => application.id === id);
    if (original === undefined) {
      throw new Error('unknown application');
    }
    return Promise.resolve({ ...original, ...changes });
  });
});

describe('KanbanBoard', () => {
  it('renders the 8 columns in meta order with their counts', async () => {
    renderBoard();
    await findBoard();
    const headings = screen
      .getAllByRole('region')
      .map((region) => within(region).getByRole('heading', { level: 2 }).textContent);
    expect(headings).toEqual([
      'Saved, 1 application',
      'Interested, 0 applications',
      'Applied, 1 application',
      'Assessment, 0 applications',
      'Interview, 2 applications',
      'Rejected, 0 applications',
      'Offer, 0 applications',
      'Withdrawn, 0 applications',
    ]);
    expect(within(column('Interview')).getAllByRole('article')).toHaveLength(2);
    expect(listApplications).toHaveBeenCalledWith({}, expect.any(AbortSignal));
  });

  it('lists only the allowed targets in the Move to menu', async () => {
    const { user } = renderBoard();
    await findBoard();
    await user.click(moveButton('Frontend Intern'));
    expect(menuItemNames()).toEqual(['Assessment', 'Interview', 'Rejected', 'Offer', 'Withdrawn']);
    await user.keyboard('{Escape}');
    await user.click(moveButton('Data Intern'));
    expect(menuItemNames()).toEqual(['Interested', 'Applied', 'Withdrawn']);
  });

  it('moves the card with a PATCH of the status and announces it when a target is chosen', async () => {
    const { user } = renderBoard();
    await findBoard();
    await user.click(moveButton('Frontend Intern'));
    await user.click(screen.getByRole('menuitem', { name: 'Interview' }));
    expect(updateMock).toHaveBeenCalledWith(10, { status: 'Interview' });
    const announcements = await screen.findAllByText('Moved Frontend Intern to Interview');
    // The board's live region plus the success toast.
    expect(announcements.length).toBeGreaterThanOrEqual(2);
  });

  it('operates the menu with Enter, Space, arrows and Escape when using the keyboard', async () => {
    const { user } = renderBoard();
    await findBoard();
    const button = moveButton('Frontend Intern');
    button.focus();

    await user.keyboard('{Enter}');
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('menuitem', { name: 'Assessment' })).toHaveFocus();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Interview' })).toHaveFocus();
    await user.keyboard('{ArrowUp}{ArrowUp}');
    expect(screen.getByRole('menuitem', { name: 'Withdrawn' })).toHaveFocus();
    await user.keyboard('{Home}');
    expect(screen.getByRole('menuitem', { name: 'Assessment' })).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(button).toHaveFocus();
    expect(button).toHaveAttribute('aria-expanded', 'false');

    await user.keyboard(' ');
    expect(screen.getByRole('menu')).toBeInTheDocument();
    await user.keyboard('{End}{Enter}');
    expect(updateMock).toHaveBeenCalledWith(10, { status: 'Withdrawn' });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('calls the API for a drop on an allowed column and not for a disallowed one', async () => {
    renderBoard();
    await findBoard();
    const dataTransfer = createDataTransfer();
    const dragged = card('Frontend Intern');

    fireEvent.dragStart(dragged, { dataTransfer });
    expect(column('Interview')).toHaveAttribute('data-drop-state', 'allowed');
    expect(within(column('Interview')).getByText('Drop here')).toBeInTheDocument();
    expect(within(column('Saved')).getByText('Not allowed')).toBeInTheDocument();
    expect(within(column('Applied')).getByText('Current column')).toBeInTheDocument();

    fireEvent.dragOver(column('Saved'), { dataTransfer });
    expect(dataTransfer.dropEffect).toBe('none');
    fireEvent.drop(column('Saved'), { dataTransfer });
    expect(updateMock).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/Frontend Intern cannot move from Applied to Saved/),
    ).toBeInTheDocument();
    expect(column('Saved')).toHaveAttribute('data-drop-state', 'idle');

    fireEvent.dragStart(dragged, { dataTransfer });
    fireEvent.dragOver(column('Interview'), { dataTransfer });
    expect(dataTransfer.dropEffect).toBe('move');
    fireEvent.drop(column('Interview'), { dataTransfer });
    await vi.waitFor(() => {
      expect(updateMock).toHaveBeenCalledWith(10, { status: 'Interview' });
    });
    expect(updateMock).toHaveBeenCalledTimes(1);
  });

  it('shows a pending state on the card while the move is in flight', async () => {
    updateMock.mockReturnValue(new Promise(() => undefined));
    const { user } = renderBoard();
    await findBoard();
    await user.click(moveButton('Frontend Intern'));
    await user.click(screen.getByRole('menuitem', { name: 'Offer' }));
    expect(await within(card('Frontend Intern')).findByText('Moving…')).toBeInTheDocument();
    expect(card('Frontend Intern')).toHaveAttribute('aria-busy', 'true');
    expect(moveButton('QA Intern')).toBeDisabled();
  });

  it('toasts the message and keeps the card in place when the move returns 409', async () => {
    updateMock.mockRejectedValue(
      new ApiError('INVALID_STATUS_TRANSITION', 'Cannot move from Applied to Offer', 409, {
        from: 'Applied',
        to: 'Offer',
        allowed: ['Withdrawn'],
      }),
    );
    const { user } = renderBoard();
    await findBoard();
    await user.click(moveButton('Frontend Intern'));
    await user.click(screen.getByRole('menuitem', { name: 'Offer' }));
    expect(
      await screen.findByText('Cannot move from Applied to Offer. Allowed moves: Withdrawn.'),
    ).toBeInTheDocument();
    expect(
      within(column('Applied')).getByRole('heading', { level: 3, name: 'Frontend Intern' }),
    ).toBeInTheDocument();
    expect(moveButton('Frontend Intern')).toBeEnabled();
  });
});
