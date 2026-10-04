import { useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { parseJobListParams, serializeJobListParams } from '../lib/jobFilters';
import type { JobListParams } from '../types/api';

/** A full replacement, or an update computed from the latest params (like `setState`). */
export type JobListParamsChange = JobListParams | ((current: JobListParams) => JobListParams);

interface PendingWrite {
  /** The rendered params the write was based on. */
  base: JobListParams;
  next: JobListParams;
}

/**
 * The Jobs page's list params, stored in the URL query string (design.md §15.2).
 *
 * Updater functions see writes that are not rendered yet, so two changes made before the
 * next render (e.g. two debounced fields committing together) both reach the URL.
 */
export function useJobListSearchParams(): [JobListParams, (change: JobListParamsChange) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useMemo(() => parseJobListParams(searchParams), [searchParams]);
  const pending = useRef<PendingWrite | null>(null);
  const setParams = useCallback(
    (change: JobListParamsChange) => {
      const current = pending.current?.base === params ? pending.current.next : params;
      const next = typeof change === 'function' ? change(current) : change;
      pending.current = { base: params, next };
      setSearchParams(serializeJobListParams(next));
    },
    [params, setSearchParams],
  );
  return [params, setParams];
}
