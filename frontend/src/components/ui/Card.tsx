import { useId } from 'react';
import type { ReactNode } from 'react';

import { cx } from '../../lib/classNames';

interface CardProps {
  /** When set, the card becomes a `<section>` labelled by this heading. */
  title?: string;
  titleAs?: 'h2' | 'h3';
  description?: string;
  /** Controls shown at the right of the header (buttons, links). */
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}

/** White surface with an optional heading row; content gets standard padding. */
export function Card({
  title,
  titleAs: Heading = 'h2',
  description,
  actions,
  children,
  className,
}: CardProps) {
  const titleId = useId();
  const surface = cx('rounded border border-ink-200 bg-white shadow-sm', className);

  if (title === undefined) {
    return (
      <div className={surface}>
        <div className="p-5">{children}</div>
      </div>
    );
  }

  return (
    <section aria-labelledby={titleId} className={surface}>
      <div className="flex items-start justify-between gap-4 border-b border-ink-200 px-5 py-4">
        <div className="min-w-0">
          <Heading id={titleId} className="text-base font-semibold text-ink-900">
            {title}
          </Heading>
          {description !== undefined && (
            <p className="mt-0.5 text-sm text-ink-600">{description}</p>
          )}
        </div>
        {actions !== undefined && <div className="flex shrink-0 gap-2">{actions}</div>}
      </div>
      {children !== undefined && <div className="p-5">{children}</div>}
    </section>
  );
}
