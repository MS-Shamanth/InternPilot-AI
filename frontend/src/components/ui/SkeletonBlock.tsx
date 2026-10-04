import { cx } from '../../lib/classNames';

interface SkeletonBlockProps {
  /** Size/shape utilities, e.g. `h-8 w-48`; defaults to a full-width text line. */
  className?: string;
}

/** One pulsing placeholder shape, hidden from assistive technology. Use inside `Skeleton`. */
export function SkeletonBlock({ className = 'h-4 w-full' }: SkeletonBlockProps) {
  return <div aria-hidden="true" className={cx('animate-pulse rounded bg-ink-200', className)} />;
}
