import { useId } from 'react';
import { Link, useParams } from 'react-router-dom';

import { isApiError } from '../api/client';
import { ApplicationSummary } from '../components/jobs/ApplicationSummary';
import { JobActions } from '../components/jobs/JobActions';
import type { JobAction } from '../components/jobs/JobActions';
import { JobFacts } from '../components/jobs/JobFacts';
import { JobFlags } from '../components/jobs/JobFlags';
import { JobSkills } from '../components/jobs/JobSkills';
import { APP_NAME } from '../components/layout/navigation';
import { MatchExplanationPanel } from '../components/match/MatchExplanationPanel';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/ui/Button';
import { buttonClasses } from '../components/ui/buttonStyles';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { SkeletonBlock } from '../components/ui/SkeletonBlock';
import { useApplicationsMeta } from '../hooks/useApplicationsMeta';
import { useApplyToJob } from '../hooks/useApplyToJob';
import { useBookmarkJob } from '../hooks/useBookmarkJob';
import { useCreateApplication } from '../hooks/useCreateApplication';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useHideJob } from '../hooks/useHideJob';
import { useJob } from '../hooks/useJob';
import { useToast } from '../hooks/useToast';
import { localIsoDate } from '../lib/format';
import { markAppliedState } from '../lib/markApplied';
import { isPlaceholderUrl, parseJobId, safeExternalUrl, similarRolesSearchUrl } from '../lib/url';
import type { JobDetail } from '../types/api';

const DETAIL_TITLE = 'Job details';
const NOT_FOUND_STATUS = 404;

function BackToJobsLink() {
  return (
    <Link to="/jobs" className="mb-4 inline-block text-sm font-medium text-pilot-700 underline">
      Back to jobs
    </Link>
  );
}

function JobNotFound() {
  return (
    <>
      <PageHeader title="Job not found" />
      <EmptyState
        title="This job does not exist"
        description="It may have been removed, or the link is incorrect."
        action={
          <Link to="/jobs" className={buttonClasses()}>
            Back to jobs
          </Link>
        }
      />
    </>
  );
}

function JobDetailSkeleton() {
  return (
    <Skeleton label="Loading job…">
      <SkeletonBlock className="h-8 w-1/2" />
      <SkeletonBlock className="h-4 w-1/3" />
      <SkeletonBlock className="h-40 w-full" />
      <SkeletonBlock className="h-64 w-full" />
    </Skeleton>
  );
}

/** Seed and fixture jobs are fictional demo companies with placeholder URLs (R11.1). */
const DEMO_SOURCES: ReadonlySet<string> = new Set(['seed', 'fixture']);

function ApplyLink({ job }: { job: JobDetail }) {
  if (DEMO_SOURCES.has(job.source) || isPlaceholderUrl(job.application_url)) {
    return (
      <p className="flex flex-wrap items-center gap-2 text-sm text-ink-700">
        Demo listing: this sample company has no live application page.
        <a
          href={similarRolesSearchUrl(job.title, job.location)}
          target="_blank"
          rel="noopener noreferrer"
          className={buttonClasses({ variant: 'secondary', size: 'sm' })}
        >
          Search for similar roles
          <span className="sr-only"> (opens in a new tab)</span>
          <span aria-hidden="true">↗</span>
        </a>
      </p>
    );
  }
  const href = safeExternalUrl(job.application_url);
  if (href === null) {
    return <p className="text-sm text-ink-600">No valid application link was provided.</p>;
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={buttonClasses({ variant: 'secondary', size: 'sm' })}
    >
      Apply on company site
      <span className="sr-only"> (opens in a new tab)</span>
      <span aria-hidden="true">↗</span>
    </a>
  );
}

function hideToastMessage(hidden: boolean): string {
  return hidden ? 'Job hidden from lists and recommendations' : 'Job is visible again';
}

/** One job with its facts, skills, description, actions and the user's application (R2.1). */
export default function JobDetailPage() {
  const params = useParams();
  const jobId = parseJobId(params.jobId);
  const titleId = useId();
  const toast = useToast();
  // Id 0 disables the query (no request is made); the invalid-id state renders below.
  const jobQuery = useJob(jobId ?? 0);
  const metaQuery = useApplicationsMeta();
  const bookmark = useBookmarkJob({
    onSuccess: (_state, { bookmarked }) => {
      toast.success(bookmarked ? 'Job bookmarked' : 'Bookmark removed');
    },
    onError: (error) => {
      toast.fromError(error);
    },
  });
  const hide = useHideJob({
    onSuccess: (_state, { hidden }) => {
      toast.success(hideToastMessage(hidden));
    },
    onError: (error) => {
      toast.fromError(error);
    },
  });
  const apply = useApplyToJob({
    onSuccess: (application) => {
      toast.success(`Marked "${application.job.title}" as applied`);
    },
    onError: (error) => {
      toast.fromError(error);
    },
  });
  const save = useCreateApplication({
    onSuccess: (application) => {
      toast.success(`Saved "${application.job.title}" to your tracker`);
    },
    onError: (error) => {
      toast.fromError(error);
    },
  });
  const job = jobQuery.data;
  useDocumentTitle(job === undefined ? null : `${job.title} · Jobs · ${APP_NAME}`);

  const today = localIsoDate(new Date());

  function pendingAction(): JobAction | null {
    if (bookmark.isPending) {
      return 'bookmark';
    }
    if (hide.isPending) {
      return 'hide';
    }
    return apply.isPending ? 'apply' : null;
  }

  function renderApplication(detail: JobDetail, busy: boolean) {
    if (detail.application !== null) {
      return <ApplicationSummary application={detail.application} today={today} />;
    }
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-ink-700">
          Not tracked yet. Save it to your tracker, or use Mark as applied once you have applied.
        </p>
        <Button
          variant="secondary"
          size="sm"
          aria-describedby={titleId}
          isLoading={save.isPending}
          disabled={busy}
          onClick={() => {
            save.mutate({ job_id: detail.id, status: 'Saved' });
          }}
        >
          Save to tracker
        </Button>
      </div>
    );
  }

  function renderJob(detail: JobDetail) {
    const pending = pendingAction();
    const busy = pending !== null || save.isPending;
    return (
      <>
        <header className="mb-6 flex flex-col gap-3">
          <div>
            <h1 id={titleId} className="text-2xl font-semibold text-ink-900">
              {detail.title}
            </h1>
            <p className="mt-1 text-sm text-ink-700">
              {detail.company} · {detail.location}
            </p>
          </div>
          <JobFlags job={detail} />
          {detail.is_hidden && (
            <p className="text-sm text-ink-700">
              This job is hidden from job lists and recommendations.
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2" aria-busy={busy || undefined}>
            <JobActions
              job={detail}
              markApplied={markAppliedState(detail.application_status, metaQuery.data?.transitions)}
              pendingAction={pending}
              disabled={save.isPending}
              describedBy={titleId}
              onToggleBookmark={() => {
                bookmark.mutate({ jobId: detail.id, bookmarked: !detail.is_bookmarked });
              }}
              onToggleHidden={() => {
                hide.mutate({ jobId: detail.id, hidden: !detail.is_hidden });
              }}
              onMarkApplied={() => {
                apply.mutate(detail.id);
              }}
            />
            <ApplyLink job={detail} />
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="flex min-w-0 flex-col gap-6">
            <MatchExplanationPanel explanation={detail.match_explanation} />
            <Card title="Overview">
              <JobFacts job={detail} today={today} />
            </Card>
            <Card title="Skills">
              <JobSkills job={detail} />
            </Card>
            <Card title="Description">
              {detail.description.trim() === '' ? (
                <p className="text-sm text-ink-600">No description provided.</p>
              ) : (
                // External text: rendered as text (React escapes it), never as HTML.
                <div className="whitespace-pre-line break-words text-sm leading-6 text-ink-800">
                  {detail.description}
                </div>
              )}
            </Card>
          </div>
          <div className="flex flex-col gap-6 self-start">
            <Card title="Your application">{renderApplication(detail, busy)}</Card>
            <Card title="Prepare">
              <ul className="flex flex-col gap-2 text-sm">
                <li>
                  <Link
                    to={`/resume?jobId=${String(detail.id)}`}
                    className="font-medium text-pilot-700 underline"
                  >
                    Analyze your resume for this job
                  </Link>
                </li>
                <li>
                  <Link
                    to={`/interview/${String(detail.id)}`}
                    className="font-medium text-pilot-700 underline"
                  >
                    Interview prep for this job
                  </Link>
                </li>
              </ul>
            </Card>
          </div>
        </div>
      </>
    );
  }

  function renderContent() {
    if (jobQuery.isPending) {
      return (
        <>
          <PageHeader title={DETAIL_TITLE} />
          <JobDetailSkeleton />
        </>
      );
    }
    if (jobQuery.isError) {
      return (
        <>
          <PageHeader title={DETAIL_TITLE} />
          <ErrorState
            title="Could not load this job"
            error={jobQuery.error}
            onRetry={() => {
              void jobQuery.refetch();
            }}
            isRetrying={jobQuery.isFetching}
          />
        </>
      );
    }
    return renderJob(jobQuery.data);
  }

  const notFound =
    jobId === null || (isApiError(jobQuery.error) && jobQuery.error.status === NOT_FOUND_STATUS);
  if (notFound) {
    return <JobNotFound />;
  }
  return (
    <>
      <BackToJobsLink />
      {renderContent()}
    </>
  );
}
