import { PAGE_SIZE_OPTIONS } from '../../lib/jobFilters';
import { Button } from '../ui/Button';
import { Select } from '../ui/Select';

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  /** 0 when `total` is 0. */
  totalPages: number;
  /** Disables the controls while the next page loads. */
  disabled?: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

function rangeText(page: number, pageSize: number, total: number): string {
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  const noun = total === 1 ? 'job' : 'jobs';
  if (first > total) {
    return `${String(total)} ${noun} in total`;
  }
  return `Showing ${String(first)}–${String(last)} of ${String(total)} ${noun}`;
}

/** Previous/Next paging with the current position and a page-size choice (R2.2, R2.6). */
export function Pagination({
  page,
  pageSize,
  total,
  totalPages,
  disabled = false,
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const lastPage = Math.max(totalPages, 1);
  // A size set through the URL (any 1–100) stays selectable.
  const sizes = PAGE_SIZE_OPTIONS.includes(pageSize)
    ? PAGE_SIZE_OPTIONS
    : [...PAGE_SIZE_OPTIONS, pageSize].sort((a, b) => a - b);
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <p className="text-sm text-ink-700">{rangeText(page, pageSize, total)}</p>
      <nav aria-label="Pagination" className="flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled || page <= 1}
          onClick={() => {
            onPageChange(Math.min(page - 1, lastPage));
          }}
        >
          Previous
        </Button>
        <span className="text-sm text-ink-800">
          Page {page} of {lastPage}
        </span>
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled || page >= lastPage}
          onClick={() => {
            onPageChange(page + 1);
          }}
        >
          Next
        </Button>
      </nav>
      <Select
        label="Jobs per page"
        value={String(pageSize)}
        disabled={disabled}
        wrapperClassName="w-32"
        onChange={(event) => {
          onPageSizeChange(Number(event.target.value));
        }}
      >
        {sizes.map((size) => (
          <option key={size} value={size}>
            {size}
          </option>
        ))}
      </Select>
    </div>
  );
}
