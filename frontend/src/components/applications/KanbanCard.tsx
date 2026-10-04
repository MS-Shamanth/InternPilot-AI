import { useId } from 'react';
import type { DragEvent } from 'react';
import { Link } from 'react-router-dom';
import { cx } from '../../lib/classNames';
import { formatDateTime } from '../../lib/format';
import type { Application, ApplicationStatus, IsoDate } from '../../types/api';
import { DeadlineText } from '../jobs/DeadlineText';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { MoveToMenu } from './MoveToMenu';

/** `dataTransfer` type carrying the dragged application id. */
export const DRAG_DATA_TYPE = 'text/plain';

interface KanbanCardProps {
  application: Application;
  today: IsoDate;
  /** Allowed targets from `/applications/meta`. */
  targets: readonly ApplicationStatus[];
  /** This card's move is in flight (no optimistic update; the server decides). */
  isPending: boolean;
  /** Another move is in flight; moves wait for it. */
  movesDisabled: boolean;
  onDragStart: (application: Application) => void;
  onDragEnd: () => void;
  onMove: (application: Application, target: ApplicationStatus) => void;
  onEdit: (application: Application) => void;
  onDelete: (application: Application) => void;
}

/** One application on the board: draggable, with a keyboard "Move to…" menu (R5.11). */
export function KanbanCard({
  application,
  today,
  targets,
  isPending,
  movesDisabled,
  onDragStart,
  onDragEnd,
  onMove,
  onEdit,
  onDelete,
}: KanbanCardProps) {
  const titleId = useId();
  const { job } = application;
  const canDrag = !movesDisabled && targets.length > 0;

  function handleDragStart(event: DragEvent<HTMLElement>) {
    if (!canDrag) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.setData(DRAG_DATA_TYPE, String(application.id));
    event.dataTransfer.effectAllowed = 'move';
    onDragStart(application);
  }

  return (
    <article
      aria-labelledby={titleId}
      aria-busy={isPending || undefined}
      draggable={canDrag}
      onDragStart={handleDragStart}
      onDragEnd={onDragEnd}
      className={cx(
        'flex flex-col gap-2 rounded border border-ink-200 bg-white p-3 shadow-sm',
        canDrag && 'cursor-grab',
        isPending && 'opacity-70',
      )}
    >
      <h3 id={titleId} className="text-sm font-semibold text-ink-900">
        <Link to={`/jobs/${String(job.id)}`} className="hover:underline">
          {job.title}
        </Link>
      </h3>
      <p className="text-xs text-ink-700">
        {job.company} · {job.location}
      </p>
      <p className="text-xs text-ink-700">
        <DeadlineText deadline={application.deadline ?? job.deadline} today={today} />
      </p>
      {application.interview_date !== null && (
        <p className="text-xs text-ink-700">
          Interview:{' '}
          <time dateTime={application.interview_date}>
            {formatDateTime(application.interview_date)}
          </time>
        </p>
      )}
      {isPending && (
        <p className="flex items-center gap-1 text-xs font-medium text-pilot-800">
          <Spinner /> Moving…
        </p>
      )}
      <div className="flex flex-wrap items-center gap-1">
        <MoveToMenu
          targets={targets}
          itemLabel={job.title}
          disabled={movesDisabled}
          onSelect={(target) => {
            onMove(application, target);
          }}
        />
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
    </article>
  );
}
