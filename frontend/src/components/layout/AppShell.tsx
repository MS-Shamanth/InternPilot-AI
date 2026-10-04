import { Suspense, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import { useMediaQuery } from '../../hooks/useMediaQuery';
import { APP_NAME, NARROW_SCREEN_QUERY, sectionTitle } from './navigation';
import { PageLoading } from './PageLoading';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export const MAIN_CONTENT_ID = 'main-content';
const SIDEBAR_ID = 'app-sidebar';

/** Skip link, sidebar, top bar and the routed page (R14.1, R14.4). */
export function AppShell() {
  const { pathname } = useLocation();
  const isNarrow = useMediaQuery(NARROW_SCREEN_QUERY);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const title = sectionTitle(pathname);
  const isPanelOpen = isNarrow && isSidebarOpen;

  useEffect(() => {
    document.title = `${title} · ${APP_NAME}`;
  }, [title]);

  useEffect(() => {
    if (!isPanelOpen) {
      return undefined;
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsSidebarOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [isPanelOpen]);

  const toggleSidebar = () => {
    setIsSidebarOpen((open) => !open);
  };
  const closeSidebar = () => {
    setIsSidebarOpen(false);
  };

  return (
    <div
      className={`min-h-screen ${isNarrow ? '' : 'grid grid-cols-[16rem_minmax(0,1fr)] grid-rows-[auto_1fr]'}`}
    >
      <a
        href={`#${MAIN_CONTENT_ID}`}
        className="sr-only z-50 rounded bg-white px-4 py-2 text-sm font-medium text-pilot-800 shadow focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to main content
      </a>
      <TopBar
        title={title}
        isNarrow={isNarrow}
        isSidebarOpen={isPanelOpen}
        sidebarId={SIDEBAR_ID}
        onToggleSidebar={toggleSidebar}
        toggleRef={toggleRef}
      />
      <Sidebar id={SIDEBAR_ID} isNarrow={isNarrow} isOpen={isPanelOpen} onNavigate={closeSidebar} />
      <main
        id={MAIN_CONTENT_ID}
        tabIndex={-1}
        className={`min-w-0 px-4 py-6 focus:outline-none ${isNarrow ? '' : 'col-start-2 px-8 py-8'}`}
      >
        <Suspense fallback={<PageLoading />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}
