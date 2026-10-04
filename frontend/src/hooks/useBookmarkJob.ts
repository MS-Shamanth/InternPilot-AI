import type { UseMutationResult } from '@tanstack/react-query';
import { bookmarkJob, unbookmarkJob } from '../api/jobs';
import type { JobState } from '../types/api';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

export interface BookmarkJobVariables {
  jobId: number;
  /** `true` sets the bookmark (`PUT`), `false` removes it (`DELETE`); both idempotent. */
  bookmarked: boolean;
}

export function useBookmarkJob(
  callbacks?: MutationCallbacks<JobState, BookmarkJobVariables>,
): UseMutationResult<JobState, Error, BookmarkJobVariables> {
  return useInvalidatingMutation({
    mutationFn: ({ jobId, bookmarked }: BookmarkJobVariables) =>
      bookmarked ? bookmarkJob(jobId) : unbookmarkJob(jobId),
    invalidates: 'jobStateChanged',
    callbacks,
  });
}
