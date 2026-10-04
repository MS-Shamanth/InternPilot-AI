import type { ReactNode } from 'react';

import { cx } from '../../lib/classNames';
import { SkeletonBlock } from './SkeletonBlock';

interface SkeletonProps {
  /** Screen-reader text announced by the status region. */
  label?: string;
  /** `SkeletonBlock`s shaped like the content; defaults to three text lines. */
  children?: ReactNode;
  className?: string;
}

/** Loading placeholder (R14.2): a `role="status"` region with hidden shapes and a text label. */
export function Skeleton({ label = 'Loading…', children, className }: SkeletonProps) {
  return (
    <div role="status" aria-busy="true" className={cx('flex flex-col gap-3', className)}>
      <span className="sr-only">{label}</span>
      {children ?? (
        <>
          <SkeletonBlock className="h-4 w-2/3" />
          <SkeletonBlock />
          <SkeletonBlock className="h-4 w-5/6" />
        </>
      )}
    </div>
  );
}
