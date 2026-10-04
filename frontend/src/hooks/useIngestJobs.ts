import type { UseMutationResult } from '@tanstack/react-query';
import { ingestJobs } from '../api/ingest';
import type { IngestRequest, IngestResult } from '../types/api';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

export function useIngestJobs(
  callbacks?: MutationCallbacks<IngestResult, IngestRequest>,
): UseMutationResult<IngestResult, Error, IngestRequest> {
  return useInvalidatingMutation({
    mutationFn: ingestJobs,
    invalidates: 'jobsIngested',
    callbacks,
  });
}
