import { cx } from '../../lib/classNames';
import { scoreBand } from '../../lib/match';
import type { ScoreBand } from '../../lib/match';

interface MatchScoreRingProps {
  /** The backend's 0–100 score. */
  score: number;
  /** Name of the score in the visible text and the label, e.g. "Match score". */
  name?: string;
  size?: 'sm' | 'md';
  /** Show the "MATCH SCORE: n/100" line; turn off when a heading already shows it. */
  showLabel?: boolean;
  className?: string;
}

const STROKE_CLASSES: Record<ScoreBand['tone'], string> = {
  success: 'stroke-success-700',
  pilot: 'stroke-pilot-700',
  warning: 'stroke-warning-700',
  danger: 'stroke-danger-700',
};
const TEXT_CLASSES: Record<ScoreBand['tone'], string> = {
  success: 'text-success-800',
  pilot: 'text-pilot-800',
  warning: 'text-warning-800',
  danger: 'text-danger-800',
};
const RADIUS = 42;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * Score gauge (R4.7, R14.5): an SVG ring with an `aria-label`, the number as visible text and a
 * band label, so color is never the only signal.
 */
export function MatchScoreRing({
  score,
  name = 'Match score',
  size = 'md',
  showLabel = true,
  className,
}: MatchScoreRingProps) {
  const shown = Math.min(100, Math.max(0, Math.round(score)));
  const band = scoreBand(shown);
  const filled = (CIRCUMFERENCE * shown) / 100;

  return (
    <div className={cx('flex items-center gap-3', className)}>
      <svg
        role="img"
        aria-label={`${name} ${String(shown)} out of 100`}
        viewBox="0 0 100 100"
        className={size === 'sm' ? 'h-14 w-14 shrink-0' : 'h-24 w-24 shrink-0'}
      >
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          strokeWidth="10"
          className="stroke-ink-200"
        />
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${String(filled)} ${String(CIRCUMFERENCE)}`}
          transform="rotate(-90 50 50)"
          className={STROKE_CLASSES[band.tone]}
        />
        <text
          x="50"
          y="50"
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-ink-900 text-[22px] font-semibold"
        >
          {`${String(shown)}/100`}
        </text>
      </svg>
      <div className="min-w-0">
        {showLabel && (
          <p className="text-sm font-semibold tracking-wide text-ink-900">
            {`${name.toUpperCase()}: ${String(shown)}/100`}
          </p>
        )}
        <p className={cx('text-sm font-medium', TEXT_CLASSES[band.tone])}>{band.label}</p>
      </div>
    </div>
  );
}
