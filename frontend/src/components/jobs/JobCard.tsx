import { useId } from 'react';
import { Link } from 'react-router-dom';
import {
  EMPLOYMENT_TYPE_OPTIONS,
  EXPERIENCE_LEVEL_OPTIONS,
  JOB_SOURCE_OPTIONS,
  WORK_MODE_OPTIONS,
  optionLabel,
} from '../../lib/enumOptions';
import { formatSalary } from '../../lib/format';
import type { MarkAppliedState } from '../../lib/markApplied';
import type { IsoDate, JobSummary } from '../../types/api';
import { MatchScoreRing } from '../match/MatchScoreRing';
import { Badge } from '../ui/Badge';
import { DeadlineText } from './DeadlineText';
import { JobActions } from './JobActions';
import type { JobAction } from './JobActions';
import { JobFlags } from './JobFlags';
import { JobSkills } from './JobSkills';

export type { JobAction } from './JobActions';

interface JobCardProps {
  job: JobSummary;
  /** The viewer's local date, `YYYY-MM-DD`, for the days-left text. */
  today: IsoDate;
  markApplied: MarkAppliedState;
  /** The action currently in flight for this job, if any. */
  pendingAction?: JobAction | null;
  onToggleBookmark: (job: JobSummary) => void;
  onToggleHidden: (job: JobSummary) => void;
  onMarkApplied: (job: JobSummary) => void;
}

/**
 * One job in the list: match score, facts, skills, the user's flags and the job actions
 * (R2.2, R2.8–R2.11, R14.5). The score's explanation is on the detail page.
 */
export function JobCard({
  job,
  today,
  markApplied,
  pendingAction = null,
  onToggleBookmark,
  onToggleHidden,
  onMarkApplied,
}: JobCardProps) {
  const titleId = useId();

  return (
    <article
      aria-labelledby={titleId}
      aria-busy={pendingAction !== null || undefined}
      className="flex flex-col gap-3 rounded border border-ink-200 bg-white p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id={titleId} className="text-base font-semibold text-ink-900">
            <Link to={`/jobs/${String(job.id)}`} className="hover:underline">
              {job.title}
            </Link>
          </h2>
          <p className="text-sm text-ink-700">
            {job.company} · {job.location}
          </p>
        </div>
        <JobFlags job={job} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <MatchScoreRing score={job.match_score} size="sm" />
        <Link
          to={`/jobs/${String(job.id)}`}
          className="text-sm font-medium text-pilot-700 underline underline-offset-2"
        >
          Why this score?<span className="sr-only"> {job.title}</span>
        </Link>
      </div>

      <ul aria-label="Job details" className="flex flex-wrap gap-1.5">
        <li>
          <Badge>{optionLabel(WORK_MODE_OPTIONS, job.work_mode)}</Badge>
        </li>
        <li>
          <Badge>{optionLabel(EMPLOYMENT_TYPE_OPTIONS, job.employment_type)}</Badge>
        </li>
        {job.experience_level !== null && (
          <li>
            <Badge>{optionLabel(EXPERIENCE_LEVEL_OPTIONS, job.experience_level)}</Badge>
          </li>
        )}
      </ul>

      <dl className="grid gap-1 text-sm text-ink-700 sm:grid-cols-2">
        <div>
          <dt className="sr-only">Salary</dt>
          <dd>{formatSalary(job)}</dd>
        </div>
        <div>
          <dt className="sr-only">Deadline</dt>
          <dd>
            <DeadlineText deadline={job.deadline} today={today} />
          </dd>
        </div>
        <div>
          <dt className="sr-only">Source</dt>
          <dd className="text-xs text-ink-600">
            Source: {optionLabel(JOB_SOURCE_OPTIONS, job.source)}
          </dd>
        </div>
      </dl>

      <JobSkills job={job} />

      <JobActions
        job={job}
        markApplied={markApplied}
        pendingAction={pendingAction}
        describedBy={titleId}
        className="border-t border-ink-200 pt-3"
        onToggleBookmark={() => {
          onToggleBookmark(job);
        }}
        onToggleHidden={() => {
          onToggleHidden(job);
        }}
        onMarkApplied={() => {
          onMarkApplied(job);
        }}
      />
    </article>
  );
}
