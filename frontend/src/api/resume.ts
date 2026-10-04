import type { ResumeAnalysis, ResumeAnalyzeRequest } from '../types/api';
import { api } from './client';

/** `POST /resume/analyze`; 422 `RESUME_EMPTY` when neither the request nor the profile has text. */
export function analyzeResume(request: ResumeAnalyzeRequest): Promise<ResumeAnalysis> {
  return api.post<ResumeAnalysis>('/resume/analyze', request);
}
