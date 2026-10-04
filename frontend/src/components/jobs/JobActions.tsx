import type { MarkAppliedState } from '../../lib/markApplied';
import { cx } from '../../lib/classNames';
import type { JobSummary } from '../../types/api';
import type { ButtonSize } from '../ui/buttonStyles';
import { Button } from '../ui/Button';

export type JobAction = 'bookmark' | 'hide' | 'apply';

interface JobActionsProps {
  job: Pick<JobSummary, 'is_bookmarked' | 'is_hidden'>;
  markApplied: MarkAppliedState;
  /** The action currently in flight, if any; every action is disabled meanwhile. */
  pendingAction?: JobAction | null;
  /** Disables every action, e.g. while another mutation for this job runs. */
  disabled?: boolean;
  /** Id of the job title, so each button is described by the job it acts on. */
  describedBy?: string;
  size?: ButtonSize;
  className?: string;
  onToggleBookmark: () => void;
  onToggleHidden: () => void;
  onMarkApplied: () => void;
}

/** Bookmark toggle, Hide/Unhide and Mark as applied (R2.8–R2.11). */
export function JobActions({
  job,
  markApplied,
  pendingAction = null,
  disabled = false,
  describedBy,
  size = 'sm',
  className,
  onToggleBookmark,
  onToggleHidden,
  onMarkApplied,
}: JobActionsProps) {
  const busy = disabled || pendingAction !== null;

  return (
    <div className={cx('flex flex-wrap gap-2', className)}>
      {/* A toggle keeps one name; aria-pressed (and the filled star) carries the state. */}
      <Button
        variant={job.is_bookmarked ? 'primary' : 'secondary'}
        size={size}
        aria-pressed={job.is_bookmarked}
        aria-describedby={describedBy}
        title={job.is_bookmarked ? 'Remove bookmark' : undefined}
        isLoading={pendingAction === 'bookmark'}
        disabled={busy}
        onClick={onToggleBookmark}
      >
        {pendingAction !== 'bookmark' && (
          <span aria-hidden="true">{job.is_bookmarked ? '★' : '☆'}</span>
        )}
        Bookmark
      </Button>
      <Button
        variant="secondary"
        size={size}
        aria-describedby={describedBy}
        isLoading={pendingAction === 'hide'}
        disabled={busy}
        onClick={onToggleHidden}
      >
        {job.is_hidden ? 'Unhide' : 'Hide'}
      </Button>
      <Button
        size={size}
        aria-describedby={describedBy}
        title={markApplied.reason ?? undefined}
        isLoading={pendingAction === 'apply'}
        disabled={busy || !markApplied.available}
        onClick={onMarkApplied}
      >
        Mark as applied
      </Button>
    </div>
  );
}
