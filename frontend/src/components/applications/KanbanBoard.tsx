import { useState } from 'react';
import type { DragEvent } from 'react';
import { allowedTargets, canMove } from '../../lib/applicationTransitions';
import type { Application, ApplicationStatus, ApplicationsMeta, IsoDate } from '../../types/api';
import { DRAG_DATA_TYPE, KanbanCard } from './KanbanCard';
import { KanbanColumn } from './KanbanColumn';
import type { DropState } from './KanbanColumn';

interface KanbanBoardProps {
  meta: ApplicationsMeta;
  applications: readonly Application[];
  today: IsoDate;
  /** The application whose move is in flight; all moves wait while one is pending. */
  pendingApplicationId: number | null;
  /** Latest move result for screen readers, e.g. "Moved Frontend Intern to Interview". */
  announcement: string;
  onMove: (application: Application, target: ApplicationStatus) => void;
  /** A card was dropped on a column it may not move to; no request is made. */
  onBlockedDrop: (application: Application, target: ApplicationStatus) => void;
  onEdit: (application: Application) => void;
  onDelete: (application: Application) => void;
}

function dropStateFor(
  meta: ApplicationsMeta,
  dragged: Application | null,
  status: ApplicationStatus,
): DropState {
  if (dragged === null) {
    return 'idle';
  }
  if (dragged.status === status) {
    return 'source';
  }
  return canMove(meta, dragged.status, status) ? 'allowed' : 'blocked';
}

/**
 * One column per status from `/applications/meta`, in its order (R5.10, R5.11). Cards move by
 * HTML5 drag and drop onto allowed columns or with each card's "Move to…" menu; the allowed
 * targets always come from `meta.transitions`.
 */
export function KanbanBoard({
  meta,
  applications,
  today,
  pendingApplicationId,
  announcement,
  onMove,
  onBlockedDrop,
  onEdit,
  onDelete,
}: KanbanBoardProps) {
  const [dragged, setDragged] = useState<Application | null>(null);
  const movesDisabled = pendingApplicationId !== null;

  function draggedFrom(event: DragEvent<HTMLElement>): Application | null {
    if (dragged !== null) {
      return dragged;
    }
    const id = Number(event.dataTransfer.getData(DRAG_DATA_TYPE));
    return applications.find((application) => application.id === id) ?? null;
  }

  function handleDrop(target: ApplicationStatus, event: DragEvent<HTMLElement>) {
    const application = draggedFrom(event);
    setDragged(null);
    if (application === null || movesDisabled || application.status === target) {
      return;
    }
    if (canMove(meta, application.status, target)) {
      onMove(application, target);
    } else {
      onBlockedDrop(application, target);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-ink-700">
        Drag a card onto a highlighted column, or use its “Move to…” menu. Only allowed moves are
        offered.
      </p>
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {meta.statuses.map((status) => {
          const cards = applications.filter((application) => application.status === status);
          return (
            <KanbanColumn
              key={status}
              status={status}
              count={cards.length}
              dropState={dropStateFor(meta, dragged, status)}
              onDrop={handleDrop}
            >
              {cards.map((application) => (
                <li key={application.id}>
                  <KanbanCard
                    application={application}
                    today={today}
                    targets={allowedTargets(meta, application.status)}
                    isPending={application.id === pendingApplicationId}
                    movesDisabled={movesDisabled}
                    onDragStart={setDragged}
                    onDragEnd={() => {
                      setDragged(null);
                    }}
                    onMove={onMove}
                    onEdit={onEdit}
                    onDelete={onDelete}
                  />
                </li>
              ))}
            </KanbanColumn>
          );
        })}
      </div>
    </div>
  );
}
