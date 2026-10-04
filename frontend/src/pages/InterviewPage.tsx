import { Link, useNavigate, useParams } from 'react-router-dom';

import { isApiError } from '../api/client';
import { InterviewPrepView } from '../components/interview/InterviewPrepView';
import { JobPicker } from '../components/jobs/JobPicker';
import { PageHeader } from '../components/layout/PageHeader';
import { buttonClasses } from '../components/ui/buttonStyles';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { SkeletonBlock } from '../components/ui/SkeletonBlock';
import { useInterviewPrep } from '../hooks/useInterviewPrep';
import { useJobs } from '../hooks/useJobs';
import { parseJobId } from '../lib/url';
import type { JobListParams } from '../types/api';

const PICKER_PARAMS: JobListParams = { page_size: 100 };
const NOT_FOUND_STATUS = 404;

/** Interview prep (R9): `/interview` picks a job, `/interview/:jobId` shows its questions. */
export default function InterviewPage() {
  const params = useParams();
  const navigate = useNavigate();
  const jobsQuery = useJobs(PICKER_PARAMS);
  const jobId = params.jobId === undefined ? null : parseJobId(params.jobId);
  // Id 0 disables the query; the invalid-id state renders below.
  const prepQuery = useInterviewPrep(jobId ?? 0);

  function renderPicker() {
    if (jobsQuery.isPending) {
      return (
        <Skeleton label="Loading jobs…">
          <SkeletonBlock className="h-16 w-full" />
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
      <JobPicker
        jobs={jobsQuery.data.items}
        value={jobId}
        hint="Questions and topics are generated for the chosen job."
        onChange={(nextId) => {
          navigate(nextId === null ? '/interview' : `/interview/${String(nextId)}`);
        }}
      />
    );
  }

  function renderPrep() {
    if (params.jobId === undefined) {
      return (
        <EmptyState
          title="Choose a job to prepare for"
          description="Pick a job above to see role, technical, skill, project and HR questions."
        />
      );
    }
    if (
      jobId === null ||
      (isApiError(prepQuery.error) && prepQuery.error.status === NOT_FOUND_STATUS)
    ) {
      return (
        <EmptyState
          title="Job not found"
          description="This job does not exist or was removed. Choose another job."
          action={
            <Link to="/jobs" className={buttonClasses({ variant: 'secondary' })}>
              Browse jobs
            </Link>
          }
        />
      );
    }
    if (prepQuery.isPending) {
      return (
        <Skeleton label="Loading interview prep…">
          <SkeletonBlock className="h-64 w-full" />
        </Skeleton>
      );
    }
    if (prepQuery.isError) {
      return (
        <ErrorState
          title="Could not load interview prep"
          error={prepQuery.error}
          isRetrying={prepQuery.isFetching}
          onRetry={() => {
            void prepQuery.refetch();
          }}
        />
      );
    }
    return <InterviewPrepView prep={prepQuery.data} />;
  }

  return (
    <>
      <PageHeader title="Interview prep" description="Practice questions for a specific job." />
      <div className="flex flex-col gap-6">
        <Card>{renderPicker()}</Card>
        {renderPrep()}
      </div>
    </>
  );
}
