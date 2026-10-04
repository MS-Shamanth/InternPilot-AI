import { daysLeftText, formatDate } from '../../lib/format';
import type { IsoDate } from '../../types/api';

interface DeadlineTextProps {
  deadline: IsoDate | null;
  /** The viewer's local date, `YYYY-MM-DD`. */
  today: IsoDate;
  /** Text before the date; the detail page omits it because its `dt` already says "Deadline". */
  prefix?: string;
}

/** "Deadline: Feb 1, 2025 · 12 days left", or "No deadline listed". */
export function DeadlineText({ deadline, today, prefix = 'Deadline: ' }: DeadlineTextProps) {
  if (deadline === null) {
    return <span>No deadline listed</span>;
  }
  const daysLeft = daysLeftText(deadline, today);
  return (
    <span>
      {prefix}
      <time dateTime={deadline}>{formatDate(deadline)}</time>
      {daysLeft !== null && <> · {daysLeft}</>}
    </span>
  );
}
