import { matchPath } from 'react-router-dom';

export interface NavItem {
  to: string;
  label: string;
}

/** Sidebar sections (R14.1, design.md §15.1). Child routes such as `/jobs/:jobId` stay active. */
export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/applications', label: 'Applications' },
  { to: '/resume', label: 'Resume analysis' },
  { to: '/interview', label: 'Interview prep' },
  { to: '/profile', label: 'Profile' },
];

export const APP_NAME = 'InternPilot AI';
export const NOT_FOUND_TITLE = 'Page not found';

/** Below Tailwind's `md` breakpoint the sidebar collapses behind a toggle. */
export const NARROW_SCREEN_QUERY = '(max-width: 767.98px)';

/** The section label shown in the top bar and document title for a pathname. */
export function sectionTitle(pathname: string): string {
  const item = NAV_ITEMS.find(({ to }) => matchPath({ path: to, end: false }, pathname) !== null);
  return item?.label ?? NOT_FOUND_TITLE;
}
