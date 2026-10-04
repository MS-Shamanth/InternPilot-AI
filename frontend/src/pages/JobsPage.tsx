import { JobCard } from '../components/jobs/JobCard';
import type { JobAction } from '../components/jobs/JobCard';
import { JobFilters } from '../components/jobs/JobFilters';
import { Pagination } from '../components/jobs/Pagination';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { SkeletonBlock } from '../components/ui/SkeletonBlock';
import { useApplicationsMeta } from '../hooks/useApplicationsMeta';
import { useApplyToJob } from '../hooks/useApplyToJob';
import { useBookmarkJob } from '../hooks/useBookmarkJob';
import { useHideJob } from '../hooks/useHideJob';
import { useJobListSearchParams } from '../hooks/useJobListSearchParams';
import { useJobs } from '../hooks/useJobs';
import { useToast } from '../hooks/useToast';
import { localIsoDate } from '../lib/format';
import { DEFAULT_PAGE, clearFilters, hasActiveFilters } from '../lib/jobFilters';
import { markAppliedState } from '../lib/markApplied';
import type { JobSummary, Page } from '../types/api';

const SKELETON_CARDS = 3;

function JobListSkeleton() {
  return (
    <Skeleton label="Loading jobs…">
      {Array.from({ length: SKELETON_CARDS }, (_, index) => (
        <SkeletonBlock key={index} className="h-48 w-full" />
      ))}
    </Skeleton>
  );
}

function resultCountText(page: Page<JobSummary> | undefined, isUpdating: boolean): string {
  if (page === undefined) {
    return '';
  }
  if (isUpdating) {
    return 'Updating results…';
  }
  if (page.total === 0) {
    return 'No jobs found';
  }
  return `${String(page.total)} ${page.total === 1 ? 'job' : 'jobs'} found`;
}

function hideToastMessage(hidden: boolean, showingHidden: boolean): string {
  if (!hidden) {
    return 'Job is visible again';
  }
  return showingHidden
    ? 'Job hidden'
    : 'Job hidden. Turn on "Include hidden jobs" to see it again.';
}

export default function JobsPage() {
  const toast = useToast();
  const [params, setParams] = useJobListSearchParams();
  const jobsQuery = useJobs(params);
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
      toast.success(hideToastMessage(hidden, params.include_hidden === true));
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

  const today = localIsoDate(new Date());
  const data = jobsQuery.data;
  const filtersActive = hasActiveFilters(params);
  const transitions = metaQuery.data?.transitions;

  function pendingActionFor(jobId: number): JobAction | null {
    if (bookmark.isPending && bookmark.variables.jobId === jobId) {
      return 'bookmark';
    }
    if (hide.isPending && hide.variables.jobId === jobId) {
      return 'hide';
    }
    if (apply.isPending && apply.variables === jobId) {
      return 'apply';
    }
    return null;
  }

  function handleClearFilters() {
    setParams(clearFilters(params));
  }

  function renderResults() {
    if (jobsQuery.isPending) {
      return <JobListSkeleton />;
    }
    if (jobsQuery.isError) {
      return (
        <ErrorState
          title="Could not load jobs"
          error={jobsQuery.error}
          onRetry={() => {
            void jobsQuery.refetch();
          }}
          isRetrying={jobsQuery.isFetching}
        />
      );
    }
    const page = jobsQuery.data;
    if (page.total === 0) {
      return filtersActive ? (
        <EmptyState
          title="No jobs match these filters"
          description="Try a broader search or remove some filters."
          action={<Button onClick={handleClearFilters}>Clear filters</Button>}
        />
      ) : (
        <EmptyState
          title="No jobs yet"
          description="Jobs come from the seeded demo data or from an import run on the backend."
          action={
            <p className="text-sm text-ink-700">
              To import jobs, run{' '}
              <code className="rounded bg-ink-100 px-1 py-0.5">
                python -m app.cli ingest --source fixture
              </code>{' '}
              in <code className="rounded bg-ink-100 px-1 py-0.5">backend/</code>.
            </p>
          }
        />
      );
    }
    if (page.items.length === 0) {
      return (
        <EmptyState
          title="This page is empty"
          description={`There are only ${String(page.total_pages)} pages of results.`}
          action={
            <Button
              onClick={() => {
                setParams({ ...params, page: DEFAULT_PAGE });
              }}
            >
              Go to the first page
            </Button>
          }
        />
      );
    }
    return (
      <div className="flex flex-col gap-4">
        <ul
          aria-label="Jobs"
          aria-busy={jobsQuery.isPlaceholderData || undefined}
          className={
            jobsQuery.isPlaceholderData ? 'flex flex-col gap-4 opacity-60' : 'flex flex-col gap-4'
          }
        >
          {page.items.map((job) => (
            <li key={job.id}>
              <JobCard
                job={job}
                today={today}
                markApplied={markAppliedState(job.application_status, transitions)}
                pendingAction={pendingActionFor(job.id)}
                onToggleBookmark={(target) => {
                  bookmark.mutate({ jobId: target.id, bookmarked: !target.is_bookmarked });
                }}
                onToggleHidden={(target) => {
                  hide.mutate({ jobId: target.id, hidden: !target.is_hidden });
                }}
                onMarkApplied={(target) => {
                  apply.mutate(target.id);
                }}
              />
            </li>
          ))}
        </ul>
        <Pagination
          page={page.page}
          pageSize={page.page_size}
          total={page.total}
          totalPages={page.total_pages}
          disabled={jobsQuery.isPlaceholderData}
          onPageChange={(next) => {
            setParams({ ...params, page: next });
          }}
          onPageSizeChange={(size) => {
            setParams({ ...params, page_size: size, page: DEFAULT_PAGE });
          }}
        />
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Internships and entry-level roles to explore and track."
      />
      <div className="grid gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <aside aria-label="Job filters">
          <JobFilters value={params} onChange={setParams} />
        </aside>
        <section aria-label="Job results" className="flex flex-col gap-4">
          <p role="status" aria-live="polite" className="text-sm font-medium text-ink-800">
            {resultCountText(data, jobsQuery.isPlaceholderData)}
          </p>
          {renderResults()}
        </section>
      </div>
    </>
  );
}
