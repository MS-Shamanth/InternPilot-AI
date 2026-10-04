import { Link } from 'react-router-dom';
import { DEADLINE_KIND_LABELS, dueInText } from '../../lib/dashboard';
import { formatDate } from '../../lib/format';
import type { UpcomingDeadline } from '../../types/api';
import { Badge } from '../ui/Badge';
import { buttonClasses } from '../ui/buttonStyles';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';

interface UpcomingDeadlinesProps {
  /** Sorted by the backend (deadline, then job id). */
  deadlines: readonly UpcomingDeadline[];
  /** Maximum rows shown; the backend already caps the list at 8. */
  limit?: number;
}

/** Deadlines in the next 14 days for tracked applications and bookmarked jobs. */
export function UpcomingDeadlines({ deadlines, limit = 8 }: UpcomingDeadlinesProps) {
  const shown = deadlines.slice(0, limit);

  return (
    <Card title="Upcoming deadlines" description="Applications and bookmarks due in 14 days.">
      {shown.length === 0 ? (
        <EmptyState
          titleAs="h3"
          title="No deadlines in the next 14 days"
          description="Bookmark jobs or track applications to see their deadlines here."
          action={
            <Link to="/jobs" className={buttonClasses({ variant: 'secondary' })}>
              Browse jobs
            </Link>
          }
        />
      ) : (
        <ul className="flex flex-col divide-y divide-ink-100">
          {shown.map((item) => (
            <li
              key={`${item.kind}-${String(item.job_id)}`}
              className="flex flex-wrap items-start justify-between gap-2 py-3 first:pt-0 last:pb-0"
            >
              <div className="min-w-0">
                <Link
                  to={`/jobs/${String(item.job_id)}`}
                  className="font-medium text-ink-900 underline-offset-2 hover:text-pilot-800 hover:underline"
                >
                  {item.title}
                </Link>
                <p className="text-sm text-ink-600">{item.company}</p>
                <p className="mt-0.5 text-sm text-ink-700">
                  <time dateTime={item.deadline}>{formatDate(item.deadline)}</time>
                  {' · '}
                  <span className="font-medium">{dueInText(item.days_left)}</span>
                </p>
              </div>
              <Badge tone={item.kind === 'application' ? 'pilot' : 'signal'}>
                {DEADLINE_KIND_LABELS[item.kind]}
              </Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
