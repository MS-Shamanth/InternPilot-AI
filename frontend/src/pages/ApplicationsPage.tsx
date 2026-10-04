import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApplicationDialog } from '../components/applications/ApplicationDialog';
import { ApplicationsTable } from '../components/applications/ApplicationsTable';
import { DeleteApplicationDialog } from '../components/applications/DeleteApplicationDialog';
import { KanbanBoard } from '../components/applications/KanbanBoard';
import { StatusFilter } from '../components/applications/StatusFilter';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/ui/Button';
import { buttonClasses } from '../components/ui/buttonStyles';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { SkeletonBlock } from '../components/ui/SkeletonBlock';
import { Tabs } from '../components/ui/Tabs';
import { useApplications } from '../hooks/useApplications';
import { useApplicationsMeta } from '../hooks/useApplicationsMeta';
import { useCreateApplication } from '../hooks/useCreateApplication';
import { useDeleteApplication } from '../hooks/useDeleteApplication';
import { useJobs } from '../hooks/useJobs';
import { useToast } from '../hooks/useToast';
import { useUpdateApplication } from '../hooks/useUpdateApplication';
import { allowedTargets } from '../lib/applicationTransitions';
import { isApplicationStatus } from '../lib/enumOptions';
import { localIsoDate } from '../lib/format';
import type {
  Application,
  ApplicationListParams,
  ApplicationStatus,
  ApplicationsMeta,
  JobListParams,
} from '../types/api';

type View = 'table' | 'board';

type DialogState =
  | { kind: 'none' }
  | { kind: 'create' }
  | { kind: 'edit'; application: Application }
  | { kind: 'delete'; application: Application };

const VIEW_PARAM = 'view';
const STATUS_PARAM = 'status';
/** The job picker lists up to 100 jobs (the API's page-size cap) sorted by title. */
const JOB_PICKER_PARAMS: JobListParams = { sort: 'title', page_size: 100 };
const NO_DIALOG: DialogState = { kind: 'none' };

/** `?view=board` → board; anything else (missing or invalid) → table. */
function parseView(value: string | null): View {
  return value === 'board' ? 'board' : 'table';
}

/** Valid, de-duplicated `?status=` values; unknown values are dropped, never sent. */
function parseStatusFilter(values: readonly string[]): ApplicationStatus[] {
  return [...new Set(values)].filter(isApplicationStatus);
}

function ApplicationsSkeleton() {
  return (
    <Skeleton label="Loading applications…">
      <SkeletonBlock className="h-10 w-64" />
      <SkeletonBlock className="h-64 w-full" />
    </Skeleton>
  );
}

interface CreateApplicationDialogProps {
  statuses: readonly ApplicationStatus[];
  onClose: () => void;
}

/** Mounted only while open, so the job list is fetched only when needed. */
function CreateApplicationDialog({ statuses, onClose }: CreateApplicationDialogProps) {
  const toast = useToast();
  const jobsQuery = useJobs(JOB_PICKER_PARAMS);
  const create = useCreateApplication({
    onError: (error) => {
      toast.fromError(error);
    },
  });
  const page = jobsQuery.data;
  return (
    <ApplicationDialog
      mode="create"
      open
      onClose={onClose}
      isSaving={create.isPending}
      statuses={statuses}
      jobPicker={{
        jobs: page?.items,
        isLoading: jobsQuery.isPending,
        error: jobsQuery.error,
        onRetry: () => {
          void jobsQuery.refetch();
        },
        truncatedTotal: page !== undefined && page.total > page.items.length ? page.total : null,
      }}
      onSubmit={async (body) => {
        const application = await create.mutateAsync(body);
        toast.success(`Added "${application.job.title}" to your tracker`);
        onClose();
      }}
    />
  );
}

interface EditApplicationDialogProps {
  application: Application;
  onClose: () => void;
}

function EditApplicationDialog({ application, onClose }: EditApplicationDialogProps) {
  const toast = useToast();
  const update = useUpdateApplication({
    onError: (error) => {
      toast.fromError(error);
    },
  });
  return (
    <ApplicationDialog
      mode="edit"
      open
      application={application}
      onClose={onClose}
      isSaving={update.isPending}
      onNoChanges={() => {
        toast.info('No changes to save');
        onClose();
      }}
      onSubmit={async (changes) => {
        const saved = await update.mutateAsync({ applicationId: application.id, changes });
        toast.success(`Saved changes to "${saved.job.title}"`);
        onClose();
      }}
    />
  );
}

/** The application tracker: a filterable table and a Kanban board (R5.9–R5.11). */
export default function ApplicationsPage() {
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const view = parseView(searchParams.get(VIEW_PARAM));
  const statusFilter = parseStatusFilter(searchParams.getAll(STATUS_PARAM));
  // The board always shows every status; the filter applies to the table only.
  const filtering = view === 'table' && statusFilter.length > 0;
  const listParams: ApplicationListParams = filtering ? { status: statusFilter } : {};
  const applicationsQuery = useApplications(listParams);
  const metaQuery = useApplicationsMeta();
  const [dialog, setDialog] = useState<DialogState>(NO_DIALOG);
  const [announcement, setAnnouncement] = useState('');
  const move = useUpdateApplication({
    onSuccess: (application) => {
      const message = `Moved ${application.job.title} to ${application.status}`;
      setAnnouncement(message);
      toast.success(message);
    },
    onError: (error) => {
      toast.fromError(error);
    },
  });
  const remove = useDeleteApplication({
    onError: (error) => {
      toast.fromError(error);
    },
  });

  const today = localIsoDate(new Date());
  const pendingApplicationId = move.isPending ? move.variables.applicationId : null;

  function updateSearch(next: { view?: View; status?: ApplicationStatus[] }) {
    const params = new URLSearchParams(searchParams);
    if (next.view !== undefined) {
      params.set(VIEW_PARAM, next.view);
    }
    if (next.status !== undefined) {
      params.delete(STATUS_PARAM);
      for (const status of next.status) {
        params.append(STATUS_PARAM, status);
      }
    }
    setSearchParams(params, { replace: true });
  }

  function closeDialog() {
    setDialog(NO_DIALOG);
  }

  function handleMove(application: Application, target: ApplicationStatus) {
    move.mutate({ applicationId: application.id, changes: { status: target } });
  }

  function handleBlockedDrop(
    meta: ApplicationsMeta,
    application: Application,
    target: ApplicationStatus,
  ) {
    const allowed = allowedTargets(meta, application.status);
    const suffix =
      allowed.length > 0 ? `Allowed moves: ${allowed.join(', ')}.` : 'No moves are allowed.';
    toast.info(
      `${application.job.title} cannot move from ${application.status} to ${target}. ${suffix}`,
    );
  }

  function handleDelete(application: Application) {
    remove.mutate(application.id, {
      onSuccess: () => {
        toast.success(`Deleted "${application.job.title}" from your tracker`);
        closeDialog();
      },
    });
  }

  const handlers = {
    onMove: handleMove,
    onEdit: (application: Application) => {
      setDialog({ kind: 'edit', application });
    },
    onDelete: (application: Application) => {
      setDialog({ kind: 'delete', application });
    },
  };

  function openCreate() {
    setDialog({ kind: 'create' });
  }

  function renderEmpty() {
    if (filtering) {
      return (
        <EmptyState
          title="No applications with these statuses"
          description="Choose other statuses or clear the filter."
          action={
            <Button
              onClick={() => {
                updateSearch({ status: [] });
              }}
            >
              Clear status filter
            </Button>
          }
        />
      );
    }
    return (
      <EmptyState
        title="No applications yet"
        description="Save a job you like or add an application you have already sent."
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <Link to="/jobs" className={buttonClasses()}>
              Find jobs to track
            </Link>
            <Button variant="secondary" onClick={openCreate}>
              Add application
            </Button>
          </div>
        }
      />
    );
  }

  function renderView(meta: ApplicationsMeta, applications: Application[]) {
    if (view === 'board') {
      return applications.length === 0 ? (
        renderEmpty()
      ) : (
        <KanbanBoard
          meta={meta}
          applications={applications}
          today={today}
          pendingApplicationId={pendingApplicationId}
          announcement={announcement}
          onBlockedDrop={(application, target) => {
            handleBlockedDrop(meta, application, target);
          }}
          {...handlers}
        />
      );
    }
    return (
      <div className="flex flex-col gap-4">
        <StatusFilter
          statuses={meta.statuses}
          value={statusFilter}
          onChange={(status) => {
            updateSearch({ status });
          }}
        />
        {applications.length === 0 ? (
          renderEmpty()
        ) : (
          <ApplicationsTable
            meta={meta}
            applications={applications}
            today={today}
            pendingApplicationId={pendingApplicationId}
            {...handlers}
          />
        )}
      </div>
    );
  }

  function renderContent() {
    if (applicationsQuery.isPending || metaQuery.isPending) {
      return <ApplicationsSkeleton />;
    }
    if (applicationsQuery.isError || metaQuery.isError) {
      return (
        <ErrorState
          title="Could not load applications"
          error={applicationsQuery.error ?? metaQuery.error}
          isRetrying={applicationsQuery.isFetching || metaQuery.isFetching}
          onRetry={() => {
            if (applicationsQuery.isError) {
              void applicationsQuery.refetch();
            }
            if (metaQuery.isError) {
              void metaQuery.refetch();
            }
          }}
        />
      );
    }
    const meta = metaQuery.data;
    const panel = renderView(meta, applicationsQuery.data);
    return (
      <>
        <Tabs<View>
          label="Applications view"
          value={view}
          onChange={(next) => {
            updateSearch({ view: next });
          }}
          items={[
            { value: 'table', label: 'Table', panel },
            { value: 'board', label: 'Board', panel },
          ]}
        />
        {dialog.kind === 'create' && (
          <CreateApplicationDialog statuses={meta.statuses} onClose={closeDialog} />
        )}
      </>
    );
  }

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title="Applications"
          description="Every application you are tracking, from saved to offer."
        />
        <Button onClick={openCreate} disabled={metaQuery.data === undefined}>
          Add application
        </Button>
      </div>
      {renderContent()}
      {dialog.kind === 'edit' && (
        <EditApplicationDialog application={dialog.application} onClose={closeDialog} />
      )}
      {dialog.kind === 'delete' && (
        <DeleteApplicationDialog
          open
          application={dialog.application}
          isDeleting={remove.isPending}
          onCancel={closeDialog}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}
