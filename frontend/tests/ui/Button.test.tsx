import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createRef } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { Button } from '../../src/components/ui/Button';
import { IconButton } from '../../src/components/ui/IconButton';

describe('Button', () => {
  it('defaults to type button and calls onClick when clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);

    const button = screen.getByRole('button', { name: 'Save' });
    await user.click(button);

    expect(button).toHaveAttribute('type', 'button');
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled, busy and announces loading when isLoading is set', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button isLoading onClick={onClick}>
        Save
      </Button>,
    );

    const button = screen.getByRole('button', { name: /save/i });
    await user.click(button);

    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(button).toHaveAccessibleName('Save (loading)');
    expect(onClick).not.toHaveBeenCalled();
  });

  it('forwards the ref and an explicit submit type when given', () => {
    const ref = createRef<HTMLButtonElement>();
    render(
      <Button ref={ref} type="submit" variant="danger">
        Delete
      </Button>,
    );

    expect(ref.current).toBe(screen.getByRole('button', { name: 'Delete' }));
    expect(ref.current).toHaveAttribute('type', 'submit');
  });
});

describe('IconButton', () => {
  it('is named by aria-label and hides its icon when rendered', () => {
    render(<IconButton aria-label="Close dialog" icon="×" />);

    const button = screen.getByRole('button', { name: 'Close dialog' });
    expect(button).toHaveAttribute('type', 'button');
    expect(button.querySelector('[aria-hidden="true"]')).toHaveTextContent('×');
  });
});
