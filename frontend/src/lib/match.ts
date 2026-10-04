/**
 * Display helpers for backend match scores (R14.5, design.md §15.2). No scoring happens here:
 * the score is the backend's number, this only picks a text label and tone for it.
 */
export interface ScoreBand {
  label: string;
  /** A design-token tone (also a `Badge` tone). */
  tone: 'success' | 'pilot' | 'warning' | 'danger';
}

/** Score bands: ≥ 80 strong, 60–79 good, 40–59 fair, < 40 low. */
export function scoreBand(score: number): ScoreBand {
  if (score >= 80) {
    return { label: 'Strong match', tone: 'success' };
  }
  if (score >= 60) {
    return { label: 'Good match', tone: 'pilot' };
  }
  if (score >= 40) {
    return { label: 'Fair match', tone: 'warning' };
  }
  return { label: 'Low match', tone: 'danger' };
}

/** Backend points (already rounded to 2 decimals) as text, e.g. `26.25`, `35`. */
export function formatPoints(points: number): string {
  return points.toLocaleString('en-US', { maximumFractionDigits: 2 });
}
