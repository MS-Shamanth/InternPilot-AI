import type { RefObject } from 'react';

import { APP_NAME } from './navigation';

interface TopBarProps {
  title: string;
  isNarrow: boolean;
  isSidebarOpen: boolean;
  sidebarId: string;
  onToggleSidebar: () => void;
  toggleRef: RefObject<HTMLButtonElement>;
}

/** Section title, narrow-screen navigation toggle and the demo-identity notice (R13.5). */
export function TopBar({
  title,
  isNarrow,
  isSidebarOpen,
  sidebarId,
  onToggleSidebar,
  toggleRef,
}: TopBarProps) {
  return (
    <header
      className={`sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-ink-200 bg-white ${isNarrow ? 'px-4' : 'col-start-2 px-8'}`}
    >
      {isNarrow && (
        <>
          <button
            ref={toggleRef}
            type="button"
            onClick={onToggleSidebar}
            aria-expanded={isSidebarOpen}
            aria-controls={sidebarId}
            className="rounded border border-ink-300 px-3 py-1.5 text-sm font-medium text-ink-800 hover:bg-ink-100"
          >
            Menu
          </button>
          <span className="hidden font-semibold text-pilot-700 sm:inline">{APP_NAME}</span>
        </>
      )}
      <p className={`text-sm font-medium text-ink-700 ${isNarrow ? 'sr-only' : ''}`}>{title}</p>
      <p className="ml-auto rounded-full border border-signal-200 bg-signal-50 px-3 py-1 text-xs text-signal-800">
        <span className="font-semibold">Demo user</span> · not real authentication
      </p>
    </header>
  );
}
