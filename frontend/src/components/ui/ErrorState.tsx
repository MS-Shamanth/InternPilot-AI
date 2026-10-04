import { toastErrorMessage } from '../../lib/toastMessages';
import { cx } from '../../lib/classNames';
import { Button } from './Button';

interface ErrorStateProps {
  title?: string;
  /** The failure; its user-facing text comes from the same helper as error toasts. */
  error?: unknown;
  /** Overrides the text derived from `error`. */
  message?: string;
  onRetry: () => void;
  /** Shows the Retry button in its loading state while a refetch runs. */
  isRetrying?: boolean;
  className?: string;
}

/** Failed-load state with a Retry action (R14.2); announced via `role="alert"`. */
export function ErrorState({
  title = 'Could not load this section',
  error,
  message,
  onRetry,
  isRetrying = false,
  className,
}: ErrorStateProps) {
  const text = message ?? toastErrorMessage(error);
  return (
    <div
      role="alert"
      className={cx(
        'flex flex-col items-center rounded border border-danger-100 bg-danger-50 px-6 py-8 text-center',
        className,
      )}
    >
      <p className="text-base font-semibold text-danger-800">{title}</p>
      <p className="mt-1 max-w-md text-sm text-ink-700">{text}</p>
      <Button variant="secondary" className="mt-4" onClick={onRetry} isLoading={isRetrying}>
        Retry
      </Button>
    </div>
  );
}
