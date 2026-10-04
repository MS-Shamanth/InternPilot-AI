import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { Tabs } from '../../src/components/ui/Tabs';

type View = 'table' | 'board' | 'list';

function TabsHarness() {
  const [view, setView] = useState<View>('table');
  return (
    <Tabs<View>
      label="Applications view"
      value={view}
      onChange={setView}
      items={[
        { value: 'table', label: 'Table', panel: <p>Table content</p> },
        { value: 'board', label: 'Board', panel: <p>Board content</p> },
        { value: 'list', label: 'List', panel: <p>List content</p> },
      ]}
    />
  );
}

describe('Tabs', () => {
  it('associates the selected tab with its visible panel when rendered', () => {
    render(<TabsHarness />);

    expect(screen.getByRole('tablist', { name: 'Applications view' })).toBeInTheDocument();
    const table = screen.getByRole('tab', { name: 'Table' });
    expect(table).toHaveAttribute('aria-selected', 'true');
    expect(table).toHaveAttribute('tabindex', '0');
    expect(screen.getByRole('tab', { name: 'Board' })).toHaveAttribute('tabindex', '-1');

    const panel = screen.getByRole('tabpanel', { name: 'Table' });
    expect(table).toHaveAttribute('aria-controls', panel.id);
    expect(panel).toHaveTextContent('Table content');
    expect(screen.queryByText('Board content')).not.toBeInTheDocument();
  });

  it('selects a tab when clicked', async () => {
    const user = userEvent.setup();
    render(<TabsHarness />);

    await user.click(screen.getByRole('tab', { name: 'Board' }));

    expect(screen.getByRole('tab', { name: 'Board' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: 'Board' })).toHaveTextContent('Board content');
  });

  it('moves focus and selection with arrow, Home and End keys', async () => {
    const user = userEvent.setup();
    render(<TabsHarness />);

    await user.tab();
    expect(screen.getByRole('tab', { name: 'Table' })).toHaveFocus();

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Board' })).toHaveFocus();
    expect(screen.getByRole('tab', { name: 'Board' })).toHaveAttribute('aria-selected', 'true');

    await user.keyboard('{End}');
    expect(screen.getByRole('tab', { name: 'List' })).toHaveFocus();

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Table' })).toHaveFocus();

    await user.keyboard('{ArrowLeft}');
    expect(screen.getByRole('tab', { name: 'List' })).toHaveAttribute('aria-selected', 'true');

    await user.keyboard('{Home}');
    expect(screen.getByRole('tab', { name: 'Table' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: 'Table' })).toHaveTextContent('Table content');
  });

  it('moves Tab from the selected tab into the panel', async () => {
    const user = userEvent.setup();
    render(<TabsHarness />);

    await user.tab();
    await user.tab();

    expect(screen.getByRole('tabpanel', { name: 'Table' })).toHaveFocus();
  });
});
