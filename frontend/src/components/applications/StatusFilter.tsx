import type { ApplicationStatus } from '../../types/api';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';

interface StatusFilterProps {
  /** Statuses from `/applications/meta`, in canonical order. */
  statuses: readonly ApplicationStatus[];
  value: readonly ApplicationStatus[];
  onChange: (value: ApplicationStatus[]) => void;
}

/** Any-of status filter for the table view (R5.9); an empty selection shows every status. */
export function StatusFilter({ statuses, value, onChange }: StatusFilterProps) {
  function toggle(status: ApplicationStatus, checked: boolean) {
    // Keep canonical order so the URL and the query key do not depend on click order.
    onChange(statuses.filter((item) => (item === status ? checked : value.includes(item))));
  }

  return (
    <fieldset className="flex flex-col gap-2 rounded border border-ink-200 bg-white p-4">
      <legend className="px-1 text-sm font-semibold text-ink-900">Filter by status</legend>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {statuses.map((status) => (
          <Checkbox
            key={status}
            label={status}
            checked={value.includes(status)}
            onChange={(event) => {
              toggle(status, event.target.checked);
            }}
          />
        ))}
        {value.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange([]);
            }}
          >
            Clear status filter
          </Button>
        )}
      </div>
    </fieldset>
  );
}
