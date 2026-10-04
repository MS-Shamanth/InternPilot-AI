import { cx } from '../../lib/classNames';

interface SpinnerProps {
  className?: string;
}

/** Decorative spinning ring; pair it with visible or screen-reader text. */
export function Spinner({ className }: SpinnerProps) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      className={cx('h-4 w-4 animate-spin', className)}
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" />
    </svg>
  );
}
