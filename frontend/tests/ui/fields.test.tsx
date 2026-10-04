import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { Checkbox } from '../../src/components/ui/Checkbox';
import { Select } from '../../src/components/ui/Select';
import { TextArea } from '../../src/components/ui/TextArea';
import { TextField } from '../../src/components/ui/TextField';

describe('TextField', () => {
  it('links label, hint and error to the input when all are given', () => {
    render(
      <TextField
        label="Email"
        hint="We never share it."
        error="Enter a valid email."
        required
        defaultValue="nope"
      />,
    );

    const input = screen.getByLabelText(/Email/);
    expect(input).toBeRequired();
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('We never share it. Error: Enter a valid email.');
    expect(screen.getByText('(required)')).toBeInTheDocument();
  });

  it('is valid with no description when it has no hint or error', async () => {
    const user = userEvent.setup();
    render(<TextField label="Full name" />);

    const input = screen.getByLabelText('Full name');
    await user.type(input, 'Ada');

    expect(input).toHaveValue('Ada');
    expect(input).not.toHaveAttribute('aria-invalid');
    expect(input).not.toHaveAttribute('aria-describedby');
  });

  it('keeps caller-supplied describedby ids alongside the error when both are given', () => {
    render(
      <>
        <p id="extra">Extra help</p>
        <TextField label="City" error="Required." aria-describedby="extra" />
      </>,
    );

    expect(screen.getByLabelText('City')).toHaveAccessibleDescription(
      'Error: Required. Extra help',
    );
  });
});

describe('TextArea', () => {
  it('associates its label and error when invalid', () => {
    render(<TextArea label="Notes" error="Too long." />);

    const textarea = screen.getByLabelText('Notes');
    expect(textarea.tagName).toBe('TEXTAREA');
    expect(textarea).toHaveAttribute('aria-invalid', 'true');
    expect(textarea).toHaveAccessibleDescription('Error: Too long.');
  });
});

describe('Select', () => {
  it('lets the user choose an option when labelled', async () => {
    const user = userEvent.setup();
    render(
      <Select label="Work mode" hint="Where you want to work." defaultValue="remote">
        <option value="remote">Remote</option>
        <option value="onsite">On-site</option>
      </Select>,
    );

    const select = screen.getByLabelText('Work mode');
    await user.selectOptions(select, 'onsite');

    expect(select).toHaveValue('onsite');
    expect(select).toHaveAccessibleDescription('Where you want to work.');
  });
});

describe('Checkbox', () => {
  it('toggles when its label is clicked and reports errors', async () => {
    const user = userEvent.setup();
    render(<Checkbox label="Open to relocation" hint="Optional." error="Please confirm." />);

    const checkbox = screen.getByRole('checkbox', { name: 'Open to relocation' });
    await user.click(screen.getByText('Open to relocation'));

    expect(checkbox).toBeChecked();
    expect(checkbox).toHaveAttribute('aria-invalid', 'true');
    expect(checkbox).toHaveAccessibleDescription('Optional. Error: Please confirm.');
  });
});
