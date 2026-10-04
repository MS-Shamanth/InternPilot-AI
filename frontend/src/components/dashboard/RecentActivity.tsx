import { Link } from 'react-router-dom';
import { ACTIVITY_TYPE_LABELS } from '../../lib/dashboard';
import { formatDateTime } from '../../lib/format';
import type { ActivityItem } from '../../types/api';
import { Badge } from '../ui/Badge';
import { buttonClasses } from '../ui/buttonStyles';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';

interface RecentActivityProps {
  /** Newest first, as sent by the backend. */
  items: readonly ActivityItem[];
}

/** The latest changes to applications, job flags and the profile. */
export function RecentActivity({ items }: RecentActivityProps) {
  return (
    <Card title="Recent activity" description="Your latest changes, newest first.">
      {items.length === 0 ? (
        <EmptyState
          titleAs="h3"
          title="No activity yet"
          description="Bookmark or save a job and your progress will show up here."
          action={
            <Link to="/jobs" className={buttonClasses({ variant: 'secondary' })}>
              Save your first job
            </Link>
          }
        />
      ) : (
        <ol className="flex flex-col divide-y divide-ink-100">
          {items.map((item) => (
            <li key={item.id} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{ACTIVITY_TYPE_LABELS[item.type]}</Badge>
                <time dateTime={item.created_at} className="text-xs text-ink-600">
                  {formatDateTime(item.created_at)}
                </time>
              </div>
              <p className="text-sm text-ink-800">{item.message}</p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
