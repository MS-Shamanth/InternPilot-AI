import { useId } from 'react';
import { Link } from 'react-router-dom';
import { statusChoices } from '../../lib/applicationTransitions';
import { formatDate, formatDateTime } from '../../lib/format';
import type { Application, ApplicationStatus, ApplicationsMeta, IsoDate } from '../../types/api';
import { DeadlineText } from '../jobs/DeadlineText';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { controlClasses } from '../ui/useFieldIds';

const NOT_SET = 'Not set';

interface ApplicationsTableProps {
  meta: ApplicationsMeta;
  /** In server order (most recently updated first). */
  applications: readonly Application[];
  today: IsoDate;
  pendingApplicationId: number | null;
  onMove: (application: Application, target: ApplicationStatus) => void;
  onEdit: (application: Application) => void;
  onDelete: (application: Application) => void;
}

interface RowProps extends Omit<ApplicationsTableProps, 'applications' | 'pendingApplicationId'> {
  application: Application;
  isPending: boolean;
  movesDisabled: boolean;
}

function Muted({ children }: { children: string }) {
  return <span className="text-ink-600">{children}</span>;
}

function ApplicationRow({
  application,
  meta,
  today,
  isPending,
  movesDisabled,
  onMove,
  onEdit,
  onDelete,
}: RowProps) {
  const selectId = useId();
  const { job } = application;
  const choices = statusChoices(meta, application.status);
  return (
    <tr aria-busy={isPending || undefined} className="border-t border-ink-200 align-top">
      <th scope="row" className="px-3 py-3 text-left font-medium">
        <Link to={`/jobs/${String(job.id)}`} className="text-pilot-700 underline">
          {job.title}
        </Link>
      </th>
      <td className="px-3 py-3">{job.company}</td>
      <td className="px-3 py-3">
        <Badge tone="signal">{application.status}</Badge>
      </td>
      <td className="px-3 py-3">
        {application.applied_at === null ? (
          <Muted>{NOT_SET}</Muted>
        ) : (
          <time dateTime={application.applied_at}>{formatDate(application.applied_at)}</time>
        )}
      </td>
      <td className="px-3 py-3">
        <DeadlineText deadline={application.deadline ?? job.deadline} today={today} prefix="" />
      </td>
      <td className="px-3 py-3">
        {application.interview_date === null ? (
          <Muted>{NOT_SET}</Muted>
        ) : (
          <time dateTime={application.interview_date}>
            {formatDateTime(application.interview_date)}
          </time>
        )}
      </td>
      <td className="px-3 py-3">
        <time dateTime={application.updated_at}>{formatDateTime(application.updated_at)}</time>
      </td>
      <td className="px-3 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={selectId} className="sr-only">
            Status for {job.title}
          </label>
          <select
            id={selectId}
            value={application.status}
            disabled={movesDisabled || choices.length < 2}
            className={controlClasses(false, 'w-36 py-1')}
            onChange={(event) => {
              const target = choices.find((status) => status === event.target.value);
              if (target !== undefined && target !== application.status) {
                onMove(application, target);
              }
            }}
          >
            {choices.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
          {isPending && <span className="text-xs font-medium text-pilot-800">Moving…</span>}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onEdit(application);
            }}
          >
            Edit<span className="sr-only"> {job.title}</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onDelete(application);
            }}
          >
            Delete<span className="sr-only"> {job.title}</span>
          </Button>
        </div>
      </td>
    </tr>
  );
}

/** Every tracked application as a table with per-row status, edit and delete (R5.9, R5.11). */
export function ApplicationsTable({
  applications,
  pendingApplicationId,
  ...rowProps
}: ApplicationsTableProps) {
  const headers = [
    'Job',
    'Company',
    'Status',
    'Applied',
    'Deadline',
    'Interview',
    'Updated',
    'Actions',
  ];
  return (
    <div className="overflow-x-auto rounded border border-ink-200 bg-white">
      <table className="w-full min-w-[60rem] text-sm text-ink-800">
        <caption className="sr-only">
          Tracked applications ({applications.length}), most recently updated first
        </caption>
        <thead className="bg-ink-50 text-left text-xs font-semibold uppercase text-ink-700">
          <tr>
            {headers.map((header) => (
              <th key={header} scope="col" className="px-3 py-2">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {applications.map((application) => (
            <ApplicationRow
              key={application.id}
              application={application}
              isPending={application.id === pendingApplicationId}
              movesDisabled={pendingApplicationId !== null}
              {...rowProps}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
