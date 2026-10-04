import { Link } from 'react-router-dom';
import type { TopRecommendation } from '../../types/api';
import { MatchScoreRing } from '../match/MatchScoreRing';
import { buttonClasses } from '../ui/buttonStyles';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';

interface TopRecommendationsProps {
  /** Ranked by the backend (score, then id). */
  items: readonly TopRecommendation[];
}

/** The best-scoring jobs the user has not applied to yet, with their backend scores. */
export function TopRecommendations({ items }: TopRecommendationsProps) {
  return (
    <Card title="Top recommendations" description="Best matches you have not applied to yet.">
      {items.length === 0 ? (
        <EmptyState
          titleAs="h3"
          title="No recommendations yet"
          description="Add skills and target roles to your profile to get matched jobs."
          action={
            <Link to="/profile" className={buttonClasses({ variant: 'secondary' })}>
              Update your profile
            </Link>
          }
        />
      ) : (
        <ul className="flex flex-col divide-y divide-ink-100">
          {items.map((item) => (
            <li
              key={item.job_id}
              className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
            >
              <div className="min-w-0">
                <Link
                  to={`/jobs/${String(item.job_id)}`}
                  className="font-medium text-ink-900 underline-offset-2 hover:text-pilot-800 hover:underline"
                >
                  {item.title}
                </Link>
                <p className="text-sm text-ink-600">{`${item.company} · ${item.location}`}</p>
              </div>
              <MatchScoreRing score={item.score} size="sm" />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
