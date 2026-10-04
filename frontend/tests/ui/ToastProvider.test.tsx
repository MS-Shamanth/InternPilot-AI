import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/api/client';
import { ToastProvider } from '../../src/components/ui/toast/ToastProvider';
import { useToast } from '../../src/hooks/useToast';

function ToastTrigger() {
  const toast = useToast();
  return (
    <>
      <button
        type="button"
        onClick={() => {
          toast.success('Profile saved');
        }}
      >
        success
      </button>
      <button
        type="button"
        onClick={() => {
          toast.info('Move not allowed');
        }}
      >
        info
      </button>
      <button
        type="button"
        onClick={() => {
          toast.error('Save failed');
        }}
      >
        error
      </button>
      <button
        type="button"
        onClick={() => {
          toast.fromError(new ApiError('NOT_FOUND', 'Job not found', 404));
        }}
      >
        api error
      </button>
    </>
  );
}

function renderToasts(
  props: { durationMs?: number; errorDurationMs?: number; maxVisible?: number } = {},
) {
  render(
    <ToastProvider {...props}>
      <ToastTrigger />
    </ToastProvider>,
  );
}

function press(name: string) {
  fireEvent.click(screen.getByRole('button', { name }));
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ToastProvider', () => {
  it('announces success and info toasts in the polite status region when shown', () => {
    renderToasts();

    press('success');
    press('info');

    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(within(status).getByText('Profile saved')).toBeInTheDocument();
    expect(within(status).getByText('Move not allowed')).toBeInTheDocument();
    expect(within(status).getByText('Success:')).toBeInTheDocument();
  });

  it('announces error toasts in the alert region when shown', () => {
    renderToasts();

    press('error');

    const alert = screen.getByRole('alert');
    expect(within(alert).getByText('Save failed')).toBeInTheDocument();
    expect(within(alert).getByText('Error:')).toBeInTheDocument();
    expect(within(screen.getByRole('status')).queryByText('Save failed')).not.toBeInTheDocument();
  });

  it('shows the envelope message when given an ApiError', () => {
    renderToasts();

    press('api error');

    expect(within(screen.getByRole('alert')).getByText('Job not found')).toBeInTheDocument();
  });

  it('removes the toast when its dismiss button is clicked', () => {
    renderToasts();
    press('success');

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }));

    expect(screen.queryByText('Profile saved')).not.toBeInTheDocument();
  });

  it('auto-dismisses a toast when its duration elapses', () => {
    renderToasts({ durationMs: 1000, errorDurationMs: 3000 });
    press('success');
    press('error');

    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(screen.getByText('Profile saved')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByText('Profile saved')).not.toBeInTheDocument();
    expect(screen.getByText('Save failed')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.queryByText('Save failed')).not.toBeInTheDocument();
  });

  it('keeps only the newest toasts when more than the maximum are shown', () => {
    renderToasts({ maxVisible: 2 });

    press('success');
    press('info');
    press('error');

    expect(screen.queryByText('Profile saved')).not.toBeInTheDocument();
    expect(screen.getByText('Move not allowed')).toBeInTheDocument();
    expect(screen.getByText('Save failed')).toBeInTheDocument();
  });
});

describe('useToast', () => {
  it('throws when used outside a ToastProvider', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    expect(() => render(<ToastTrigger />)).toThrow('useToast must be used inside <ToastProvider>.');
  });
});
