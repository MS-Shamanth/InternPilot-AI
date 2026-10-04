import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRef, useState } from 'react';
import { describe, expect, it } from 'vitest';

import { Button } from '../../src/components/ui/Button';
import { Dialog } from '../../src/components/ui/Dialog';
import { TextField } from '../../src/components/ui/TextField';

interface HarnessProps {
  closeOnBackdropClick?: boolean;
  focusField?: boolean;
}

function DialogHarness({ closeOnBackdropClick, focusField = false }: HarnessProps) {
  const [open, setOpen] = useState(false);
  const fieldRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button
        onClick={() => {
          setOpen(true);
        }}
      >
        Edit notes
      </Button>
      <Dialog
        open={open}
        onClose={() => {
          setOpen(false);
        }}
        title="Edit application"
        description="Update notes for this role."
        closeOnBackdropClick={closeOnBackdropClick}
        initialFocusRef={focusField ? fieldRef : undefined}
        footer={
          <Button
            onClick={() => {
              setOpen(false);
            }}
          >
            Save
          </Button>
        }
      >
        <TextField ref={fieldRef} label="Notes" />
      </Dialog>
    </>
  );
}

async function openDialog(props: HarnessProps = {}) {
  const user = userEvent.setup();
  render(<DialogHarness {...props} />);
  await user.click(screen.getByRole('button', { name: 'Edit notes' }));
  return user;
}

describe('Dialog', () => {
  it('renders an accessible modal with focus inside when opened', async () => {
    await openDialog();

    const dialog = screen.getByRole('dialog', { name: 'Edit application' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleDescription('Update notes for this role.');
    expect(dialog).toHaveFocus();
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('focuses the initial focus element when one is given', async () => {
    await openDialog({ focusField: true });

    expect(screen.getByLabelText('Notes')).toHaveFocus();
  });

  it('closes on Escape and returns focus to the trigger', async () => {
    const user = await openDialog();

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Edit notes' })).toHaveFocus();
    expect(document.body.style.overflow).toBe('');
  });

  it('closes when the close button is pressed', async () => {
    const user = await openDialog();

    await user.click(screen.getByRole('button', { name: 'Close dialog' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes on backdrop click unless backdrop closing is disabled', async () => {
    const user = await openDialog();
    await user.click(screen.getByTestId('dialog-backdrop'));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('stays open on backdrop click when closeOnBackdropClick is false', async () => {
    const user = await openDialog({ closeOnBackdropClick: false });

    await user.click(screen.getByTestId('dialog-backdrop'));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('traps Tab and Shift+Tab inside the dialog when cycling', async () => {
    const user = await openDialog();
    const close = screen.getByRole('button', { name: 'Close dialog' });
    const notes = screen.getByLabelText('Notes');
    const save = screen.getByRole('button', { name: 'Save' });

    await user.tab();
    expect(close).toHaveFocus();
    await user.tab();
    expect(notes).toHaveFocus();
    await user.tab();
    expect(save).toHaveFocus();
    await user.tab();
    expect(close).toHaveFocus();
    await user.tab({ shift: true });
    expect(save).toHaveFocus();
  });

  it('moves Shift+Tab from the dialog itself to the last element', async () => {
    const user = await openDialog();

    await user.tab({ shift: true });

    expect(screen.getByRole('button', { name: 'Save' })).toHaveFocus();
  });
});
