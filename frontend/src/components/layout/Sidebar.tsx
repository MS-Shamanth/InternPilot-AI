import { NavLink } from 'react-router-dom';

import { APP_NAME, NAV_ITEMS } from './navigation';

interface SidebarProps {
  id: string;
  /** Narrow screens render the sidebar as a panel below the top bar. */
  isNarrow: boolean;
  /** Only meaningful on narrow screens; the sidebar is always shown otherwise. */
  isOpen: boolean;
  onNavigate: () => void;
}

function linkClassName({ isActive }: { isActive: boolean }): string {
  const base = 'block rounded px-3 py-2 text-sm font-medium transition-colors';
  return isActive
    ? `${base} bg-pilot-50 text-pilot-800`
    : `${base} text-ink-700 hover:bg-ink-100 hover:text-ink-900`;
}

/** Persistent primary navigation (R14.1); `NavLink` sets `aria-current="page"` on the active item. */
export function Sidebar({ id, isNarrow, isOpen, onNavigate }: SidebarProps) {
  const position = isNarrow
    ? 'fixed inset-x-0 bottom-0 top-14 z-30 overflow-y-auto shadow-lg'
    : 'sticky top-0 col-start-1 row-span-2 row-start-1 h-screen self-start';

  return (
    <aside
      id={id}
      hidden={isNarrow && !isOpen}
      className={`flex w-full flex-col border-r border-ink-200 bg-white ${position}`}
    >
      {!isNarrow && (
        <div className="flex h-14 items-center border-b border-ink-200 px-5">
          <span className="text-lg font-semibold text-pilot-700">{APP_NAME}</span>
        </div>
      )}
      <nav aria-label="Primary" className="flex-1 px-3 py-4">
        <ul className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} className={linkClassName} onClick={onNavigate}>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
