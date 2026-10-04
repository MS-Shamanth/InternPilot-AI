import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/api/client';
import { Badge } from '../../src/components/ui/Badge';
import { Button } from '../../src/components/ui/Button';
import { Card } from '../../src/components/ui/Card';
import { EmptyState } from '../../src/components/ui/EmptyState';
import { ErrorState } from '../../src/components/ui/ErrorState';
import { Skeleton } from '../../src/components/ui/Skeleton';
import { UNEXPECTED_ERROR_MESSAGE } from '../../src/lib/toastMessages';

describe('Skeleton', () => {
  it('exposes a status labelled "Loading…" with hidden shapes when rendered', () => {
    const { container } = render(<Skeleton />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading…');
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(3);
  });

  it('uses a custom label when given', () => {
    render(<Skeleton label="Loading jobs…" />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading jobs…');
  });
});

describe('EmptyState', () => {
  it('shows the title, description and next action when given', async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(
      <EmptyState
        title="No applications yet"
        description="Save a job to start tracking it."
        action={<Button onClick={onAction}>Browse jobs</Button>}
      />,
    );

    expect(screen.getByRole('heading', { name: 'No applications yet' })).toBeInTheDocument();
    expect(screen.getByText('Save a job to start tracking it.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Browse jobs' }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});

describe('ErrorState', () => {
  it('shows the ApiError message and calls onRetry when Retry is pressed', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <ErrorState
        error={new ApiError('DATABASE_UNAVAILABLE', 'Database unavailable.', 503)}
        onRetry={onRetry}
      />,
    );

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Could not load this section');
    expect(alert).toHaveTextContent('Database unavailable.');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('falls back to the generic message for unknown errors', () => {
    render(<ErrorState error={new Error('boom')} onRetry={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent(UNEXPECTED_ERROR_MESSAGE);
  });

  it('disables Retry while retrying', () => {
    render(<ErrorState message="Offline." onRetry={vi.fn()} isRetrying />);

    expect(screen.getByRole('button', { name: /retry/i })).toBeDisabled();
  });
});

describe('Badge', () => {
  it('renders its text when given a tone', () => {
    render(<Badge tone="success">Offer</Badge>);

    expect(screen.getByText('Offer')).toBeInTheDocument();
  });
});

describe('Card', () => {
  it('is a region labelled by its title when a title is given', () => {
    render(
      <Card title="Upcoming deadlines" description="Next 14 days" actions={<Button>View</Button>}>
        <p>Body</p>
      </Card>,
    );

    const region = screen.getByRole('region', { name: 'Upcoming deadlines' });
    expect(region).toHaveTextContent('Next 14 days');
    expect(region).toHaveTextContent('Body');
  });

  it('renders plain content without a region when untitled', () => {
    render(<Card>Plain</Card>);

    expect(screen.queryByRole('region')).not.toBeInTheDocument();
    expect(screen.getByText('Plain')).toBeInTheDocument();
  });
});
