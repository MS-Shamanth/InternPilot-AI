import { Link } from 'react-router-dom';
import { formatPercent } from '../../lib/dashboard';
import type { Dashboard } from '../../types/api';

type StatFields = Pick<
  Dashboard,
  | 'total_jobs_discovered'
  | 'matching_jobs'
  | 'applications_submitted'
  | 'interviews_scheduled'
  | 'offers_received'
  | 'response_rate'
>;

interface StatCardsProps {
  stats: StatFields;
}

interface Stat {
  key: keyof StatFields;
  label: string;
  value: string;
  hint: string;
  link?: { to: string; text: string };
}

function buildStats(stats: StatFields): Stat[] {
  return [
    {
      key: 'total_jobs_discovered',
      label: 'Total jobs discovered',
      value: String(stats.total_jobs_discovered),
      hint: 'Every job imported into InternPilot.',
      link: { to: '/jobs', text: 'Browse jobs' },
    },
    {
      key: 'matching_jobs',
      label: 'Matching jobs',
      value: String(stats.matching_jobs),
      hint: 'Jobs you have not hidden with a match score of 60 or more.',
    },
    {
      key: 'applications_submitted',
      label: 'Applications submitted',
      value: String(stats.applications_submitted),
      hint: 'Applications you have sent, including ones that moved to a later stage.',
      link: { to: '/applications', text: 'View applications' },
    },
    {
      key: 'interviews_scheduled',
      label: 'Interviews scheduled',
      value: String(stats.interviews_scheduled),
      hint: 'In the Interview stage or with an upcoming interview date.',
      link: { to: '/applications?view=board', text: 'Open the board' },
    },
    {
      key: 'offers_received',
      label: 'Offers received',
      value: String(stats.offers_received),
      hint: 'Applications in the Offer status.',
    },
    {
      key: 'response_rate',
      label: 'Response rate',
      value: formatPercent(stats.response_rate),
      hint: 'Submitted applications that reached Assessment, Interview, Offer or Rejected.',
    },
  ];
}

/** Headline metrics as a description list; every value comes from the backend (R6.1). */
export function StatCards({ stats }: StatCardsProps) {
  return (
    <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {buildStats(stats).map((stat) => (
        <div
          key={stat.key}
          className="flex flex-col rounded border border-ink-200 bg-white p-5 shadow-sm"
        >
          <dt className="text-sm font-medium text-ink-700">{stat.label}</dt>
          <dd className="mt-1 text-3xl font-semibold tabular-nums text-ink-900">{stat.value}</dd>
          <dd className="mt-1 text-xs text-ink-600">{stat.hint}</dd>
          {stat.link !== undefined && (
            <dd className="mt-3">
              <Link
                to={stat.link.to}
                className="text-sm font-medium text-pilot-700 underline-offset-2 hover:underline"
              >
                {stat.link.text}
              </Link>
            </dd>
          )}
        </div>
      ))}
    </dl>
  );
}
