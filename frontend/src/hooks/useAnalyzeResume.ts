import type { UseMutationResult } from '@tanstack/react-query';
import { analyzeResume } from '../api/resume';
import { queryKeys } from '../lib/queryKeys';
import type { ResumeAnalysis, ResumeAnalyzeRequest } from '../types/api';
import { useInvalidatingMutation } from './useInvalidatingMutation';
import type { MutationCallbacks } from './useInvalidatingMutation';

/** `POST /resume/analyze`: a computation that changes no server state, so nothing is invalidated. */
export function useAnalyzeResume(
  callbacks?: MutationCallbacks<ResumeAnalysis, ResumeAnalyzeRequest>,
): UseMutationResult<ResumeAnalysis, Error, ResumeAnalyzeRequest> {
  return useInvalidatingMutation({
    mutationFn: analyzeResume,
    mutationKey: queryKeys.resume(),
    callbacks,
  });
}
