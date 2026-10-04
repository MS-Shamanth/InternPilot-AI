import { Link } from 'react-router-dom';
import { ApplicationsOverTimeChart } from '../components/dashboard/ApplicationsOverTimeChart';
import { RecentActivity } from '../components/dashboard/RecentActivity';
import { ScoreDistributionChart } from '../components/dashboard/ScoreDistributionChart';
import { StatCards } from '../components/dashboard/StatCards';
import { StatusBreakdownChart } from '../components/dashboard/StatusBreakdownChart';
import { TopRecommendations } from '../components/dashboard/TopRecommendations';
import { UpcomingDeadlines } from '../components/dashboard/UpcomingDeadlines';
import { PageHeader } from '../components/layout/PageHeader';
import { buttonClasses } from '../components/ui/buttonStyles';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { SkeletonBlock } from '../components/ui/SkeletonBlock';
import { useDashboard } from '../hooks/useDashboard';
import { isDashboardEmpty } from '../lib/dashboard';
import type { Dashboard } from '../types/api';

function DashboardSkeleton() {
  return (
    <Skeleton label="Loading dashboard…">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[1, 2, 3, 4, 5, 6].map((key) => (
          <SkeletonBlock key={key} className="h-28 w-full" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <SkeletonBlock className="h-72 w-full" />
        <SkeletonBlock className="h-72 w-full" />
      </div>
    </Skeleton>
  );
}

function EmptyDashboard() {
  return (
    <EmptyState
      title="Your dashboard is empty"
      description="Add your skills and target roles, then browse jobs to save or apply. Your metrics, deadlines and activity appear here as soon as there is data."
      action={
        <div className="flex flex-wrap justify-center gap-2">
          <Link to="/profile" className={buttonClasses()}>
            Complete your profile
          </Link>
          <Link to="/jobs" className={buttonClasses({ variant: 'secondary' })}>
            Browse jobs
          </Link>
        </div>
      }
    />
  );
}

/** Sections in reading order. */
function DashboardSections({ dashboard }: { dashboard: Dashboard }) {
  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="dashboard-summary-heading">
        <h2 id="dashboard-summary-heading" className="sr-only">
          Summary
        </h2>
        <StatCards stats={dashboard} />
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <StatusBreakdownChart items={dashboard.status_breakdown} />
        <ApplicationsOverTimeChart weeks={dashboard.applications_over_time} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <TopRecommendations items={dashboard.top_recommendations} />
        <ScoreDistributionChart buckets={dashboard.score_distribution} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <UpcomingDeadlines deadlines={dashboard.upcoming_deadlines} />
        <RecentActivity items={dashboard.recent_activity} />
      </div>
    </div>
  );
}

/** Career dashboard (R6): every metric is computed by the backend and only displayed here. */
export default function DashboardPage() {
  const dashboardQuery = useDashboard();

  function renderContent() {
    if (dashboardQuery.isPending) {
      return <DashboardSkeleton />;
    }
    if (dashboardQuery.isError) {
      return (
        <ErrorState
          title="Could not load the dashboard"
          error={dashboardQuery.error}
          isRetrying={dashboardQuery.isFetching}
          onRetry={() => {
            void dashboardQuery.refetch();
          }}
        />
      );
    }
    if (isDashboardEmpty(dashboardQuery.data)) {
      return <EmptyDashboard />;
    }
    return <DashboardSections dashboard={dashboardQuery.data} />;
  }

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Your application pipeline, upcoming deadlines and recent activity."
      />
      {renderContent()}
    </>
  );
}
