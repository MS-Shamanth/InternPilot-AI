import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { formatDate, formatDateTime } from '../../lib/format';
import type { Application, IsoDate } from '../../types/api';
import { Badge } from '../ui/Badge';
import { DeadlineText } from './DeadlineText';

const NOT_SET = 'Not set';

interface ApplicationSummaryProps {
  application: Application;
  /** The viewer's local date, `YYYY-MM-DD`, for the days-left text. */
  today: IsoDate;
}

interface Detail {
  label: string;
  value: ReactNode;
}

function RecruiterValue({ name, email }: { name: string | null; email: string | null }) {
  if (name === null && email === null) {
    return <>{NOT_SET}</>;
  }
  return (
    <span className="flex flex-col">
      {name !== null && <span>{name}</span>}
      {email !== null && (
        <a href={`mailto:${email}`} className="text-pilot-700 underline">
          {email}
        </a>
      )}
    </span>
  );
}

/** The user's tracker record for one job, read-only, with a link to edit it (R5.1). */
export function ApplicationSummary({ application, today }: ApplicationSummaryProps) {
  const details: Detail[] = [
    {
      label: 'Applied on',
      value:
        application.applied_at === null ? (
          NOT_SET
        ) : (
          <time dateTime={application.applied_at}>{formatDate(application.applied_at)}</time>
        ),
    },
    {
      label: 'Application deadline',
      value:
        application.deadline === null ? (
          NOT_SET
        ) : (
          <DeadlineText deadline={application.deadline} today={today} prefix="" />
        ),
    },
    {
      label: 'Interview',
      value:
        application.interview_date === null ? (
          NOT_SET
        ) : (
          <time dateTime={application.interview_date}>
            {formatDateTime(application.interview_date)}
          </time>
        ),
    },
    {
      label: 'Recruiter',
      value: (
        <RecruiterValue name={application.recruiter_name} email={application.recruiter_email} />
      ),
    },
    {
      label: 'Notes',
      value:
        application.notes.trim() === '' ? (
          'No notes'
        ) : (
          <span className="whitespace-pre-line">{application.notes}</span>
        ),
    },
    { label: 'Outcome', value: application.outcome ?? NOT_SET },
  ];

  return (
    <div className="flex flex-col gap-4">
      <p>
        <Badge tone="signal">Status: {application.status}</Badge>
      </p>
      <dl className="flex flex-col gap-3 text-sm">
        {details.map(({ label, value }) => (
          <div key={label}>
            <dt className="font-medium text-ink-600">{label}</dt>
            <dd className="break-words text-ink-900">{value}</dd>
          </div>
        ))}
      </dl>
      <Link to="/applications" className="text-sm font-medium text-pilot-700 underline">
        Manage in Applications
      </Link>
    </div>
  );
}
