/**
 * Raw colors for Recharts, which draws SVG and cannot use Tailwind classes. Each value mirrors a
 * token in `tailwind.config.ts` (a unit test keeps them in sync); do not add ad-hoc hex values.
 */
export const CHART_COLORS = {
  /** pilot-700: primary series fill. */
  primary: '#0f766e',
  /** signal-700: accent series fill. */
  accent: '#b45309',
  /** ink-200: grid lines. */
  grid: '#e2e8f0',
  /** ink-600: axis text and ticks (4.5:1 on white). */
  axis: '#475569',
} as const;
