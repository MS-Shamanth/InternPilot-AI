import type { ReactNode } from 'react';

import { cx } from '../../lib/classNames';

export type BadgeTone = 'neutral' | 'pilot' | 'signal' | 'success' | 'warning' | 'danger';

interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}

/** Text shades are 700/800 on 50 fills, so every tone meets 4.5:1 (R14.4). */
const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'border-ink-200 bg-ink-100 text-ink-700',
  pilot: 'border-pilot-200 bg-pilot-50 text-pilot-800',
  signal: 'border-signal-200 bg-signal-50 text-signal-800',
  success: 'border-success-100 bg-success-50 text-success-800',
  warning: 'border-warning-100 bg-warning-50 text-warning-800',
  danger: 'border-danger-100 bg-danger-50 text-danger-800',
};

/** Small inline label; the text carries the meaning, the tone only reinforces it. */
export function Badge({ tone = 'neutral', children, className }: BadgeProps) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
