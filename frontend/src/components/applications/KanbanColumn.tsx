import { useId } from 'react';
import type { DragEvent, ReactNode } from 'react';
import { cx } from '../../lib/classNames';
import type { ApplicationStatus } from '../../types/api';

/** How a column relates to the card being dragged. */
export type DropState = 'idle' | 'source' | 'allowed' | 'blocked';

interface KanbanColumnProps {
  status: ApplicationStatus;
  count: number;
  dropState: DropState;
  /** Called for every drop; the board decides whether the move is allowed. */
  onDrop: (status: ApplicationStatus, event: DragEvent<HTMLElement>) => void;
  /** `<li>` elements, one per card. */
  children: ReactNode;
}

/** Text cue shown during a drag, so the state is never signalled by color alone (R14.4). */
const DROP_CUES: Record<DropState, string | null> = {
  idle: null,
  source: 'Current column',
  allowed: 'Drop here',
  blocked: 'Not allowed',
};

const DROP_CLASSES: Record<DropState, string> = {
  idle: 'border-ink-200 bg-ink-50',
  source: 'border-ink-300 bg-ink-50',
  allowed: 'border-2 border-dashed border-pilot-700 bg-pilot-50',
  blocked: 'border-ink-200 bg-ink-100 opacity-70',
};

/** One status column: a labelled region with a count and a list of cards. */
export function KanbanColumn({ status, count, dropState, onDrop, children }: KanbanColumnProps) {
  const headingId = useId();
  const cue = DROP_CUES[dropState];

  function handleDragOver(event: DragEvent<HTMLElement>) {
    if (dropState === 'allowed') {
      // Accepting the drag over this column is what enables a drop here.
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
    } else {
      event.dataTransfer.dropEffect = 'none';
    }
  }

  return (
    <section
      aria-labelledby={headingId}
      data-drop-state={dropState}
      onDragOver={handleDragOver}
      onDrop={(event) => {
        event.preventDefault();
        onDrop(status, event);
      }}
      className={cx(
        'flex w-72 shrink-0 flex-col gap-3 rounded border p-3 transition-colors',
        DROP_CLASSES[dropState],
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id={headingId} className="text-sm font-semibold text-ink-900">
          {status}
          <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-xs font-medium text-ink-700">
            <span className="sr-only">, </span>
            {count}
            <span className="sr-only">{count === 1 ? ' application' : ' applications'}</span>
          </span>
        </h2>
        {cue !== null && (
          <span
            className={cx(
              'text-xs font-medium',
              dropState === 'allowed' ? 'text-pilot-800' : 'text-ink-700',
            )}
          >
            {dropState === 'blocked' && <span aria-hidden="true">⊘ </span>}
            {cue}
          </span>
        )}
      </div>
      {count === 0 ? (
        <p className="text-xs text-ink-600">No applications</p>
      ) : (
        <ul aria-label={`${status} applications`} className="flex flex-col gap-2">
          {children}
        </ul>
      )}
    </section>
  );
}
