import { lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './components/layout/AppShell';

// Pages are code-split; AppShell renders a skeleton while a page chunk loads.
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const JobsPage = lazy(() => import('./pages/JobsPage'));
const JobDetailPage = lazy(() => import('./pages/JobDetailPage'));
const ApplicationsPage = lazy(() => import('./pages/ApplicationsPage'));
const ResumePage = lazy(() => import('./pages/ResumePage'));
const InterviewPage = lazy(() => import('./pages/InterviewPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

/** Route table (R14.1, design.md §15.1). Must be rendered inside a router. */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:jobId" element={<JobDetailPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="resume" element={<ResumePage />} />
        <Route path="interview" element={<InterviewPage />} />
        <Route path="interview/:jobId" element={<InterviewPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
