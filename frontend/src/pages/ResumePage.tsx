import { useState } from 'react';
import type { FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';

import { isApiError } from '../api/client';
import { JobPicker } from '../components/jobs/JobPicker';
import { PageHeader } from '../components/layout/PageHeader';
import { ResumeResults } from '../components/resume/ResumeResults';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { SkeletonBlock } from '../components/ui/SkeletonBlock';
import { TextArea } from '../components/ui/TextArea';
import { useAnalyzeResume } from '../hooks/useAnalyzeResume';
import { useJobs } from '../hooks/useJobs';
import { useToast } from '../hooks/useToast';
import { parseJobId } from '../lib/url';
import type { JobListParams } from '../types/api';

/** Picker options: the user's best matches first (backend default sort). */
const PICKER_PARAMS: JobListParams = { page_size: 100 };
const RESUME_TEXT_MAX_LENGTH = 50_000;
const RESUME_EMPTY = 'RESUME_EMPTY';

function isResumeEmpty(error: unknown): boolean {
  return isApiError(error) && error.code === RESUME_EMPTY;
}

/** Resume analysis (R8): pick a job, optionally paste a resume, see the backend's analysis. */
export default function ResumePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const jobsQuery = useJobs(PICKER_PARAMS);
  const [resumeText, setResumeText] = useState('');
  const toast = useToast();
  const analyze = useAnalyzeResume({
    onError: (error) => {
      if (!isResumeEmpty(error)) {
        toast.fromError(error);
      }
    },
  });

  const jobId = parseJobId(searchParams.get('jobId'));
  const resumeError =
    analyze.isError && isResumeEmpty(analyze.error) ? analyze.error.message : undefined;
  const analysis =
    analyze.data !== undefined && analyze.data.job_id === jobId ? analyze.data : null;

  function handleJobChange(nextId: number | null) {
    analyze.reset();
    setSearchParams(nextId === null ? {} : { jobId: String(nextId) }, { replace: true });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (jobId === null) {
      return;
    }
    analyze.mutate({ job_id: jobId, resume_text: resumeText.trim() === '' ? null : resumeText });
  }

  function renderForm() {
    if (jobsQuery.isPending) {
      return (
        <Skeleton label="Loading jobs…">
          <SkeletonBlock className="h-40 w-full" />
        </Skeleton>
      );
    }
    if (jobsQuery.isError) {
      return (
        <ErrorState
          title="Could not load jobs"
          error={jobsQuery.error}
          isRetrying={jobsQuery.isFetching}
          onRetry={() => {
            void jobsQuery.refetch();
          }}
        />
      );
    }
    return (
      <form aria-label="Resume analysis" className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <JobPicker
          jobs={jobsQuery.data.items}
          value={jobId}
          onChange={handleJobChange}
          hint="The job to compare your resume against."
        />
        <TextArea
          label="Resume text (optional)"
          hint="Leave blank to analyze the resume saved in your profile."
          rows={10}
          maxLength={RESUME_TEXT_MAX_LENGTH}
          value={resumeText}
          error={resumeError}
          onChange={(event) => {
            setResumeText(event.target.value);
          }}
        />
        <div>
          <Button type="submit" disabled={jobId === null} isLoading={analyze.isPending}>
            Analyze resume
          </Button>
        </div>
      </form>
    );
  }

  return (
    <>
      <PageHeader
        title="Resume analysis"
        description="Compare your resume and profile against a specific job."
      />
      <div className="flex flex-col gap-6">
        <Card>{renderForm()}</Card>
        {analysis !== null && <ResumeResults analysis={analysis} />}
      </div>
    </>
  );
}
