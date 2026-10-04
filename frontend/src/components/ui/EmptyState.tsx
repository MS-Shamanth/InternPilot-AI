import type { ReactNode } from 'react';

import { cx } from '../../lib/classNames';

interface EmptyStateProps {
  title: string;
  description?: string;
  /** The next step for the user (a Button or Link), per "actionable over decorative". */
  action?: ReactNode;
  titleAs?: 'h2' | 'h3';
  className?: string;
}

/** Shown when a list or section has no data yet (R14.2). */
export function EmptyState({
  title,
  description,
  action,
  titleAs: Heading = 'h2',
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cx(
        'flex flex-col items-center rounded border border-dashed border-ink-300 bg-white px-6 py-10 text-center',
        className,
      )}
    >
      <Heading className="text-base font-semibold text-ink-900">{title}</Heading>
      {description !== undefined && (
        <p className="mt-1 max-w-md text-sm text-ink-600">{description}</p>
      )}
      {action !== undefined && <div className="mt-4">{action}</div>}
    </div>
  );
}
