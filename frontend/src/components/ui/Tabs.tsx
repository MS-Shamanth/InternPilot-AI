import { useId, useRef } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';

import { cx } from '../../lib/classNames';

export interface TabItem<T extends string> {
  value: T;
  label: string;
  panel: ReactNode;
}

interface TabsProps<T extends string> {
  /** Accessible name of the tab list. */
  label: string;
  items: readonly TabItem<T>[];
  /** Controlled selection, e.g. synced with `?view=` in the URL. */
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

/**
 * WAI-ARIA tabs with automatic activation: the selected tab is the only one in the Tab order;
 * ArrowLeft/ArrowRight (wrapping), Home and End move focus and select.
 */
export function Tabs<T extends string>({ label, items, value, onChange, className }: TabsProps<T>) {
  const baseId = useId();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const selectedIndex = Math.max(
    0,
    items.findIndex((item) => item.value === value),
  );

  function selectAt(index: number) {
    const item = items[index];
    if (item === undefined) {
      return;
    }
    tabRefs.current[index]?.focus();
    if (item.value !== value) {
      onChange(item.value);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const count = items.length;
    const target = nextIndex(event.key, index, count);
    if (target === null) {
      return;
    }
    event.preventDefault();
    selectAt(target);
  }

  return (
    <div className={className}>
      <div role="tablist" aria-label={label} className="flex gap-1 border-b border-ink-200">
        {items.map((item, index) => {
          const isSelected = index === selectedIndex;
          return (
            <button
              key={item.value}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              type="button"
              role="tab"
              id={`${baseId}-tab-${item.value}`}
              aria-selected={isSelected}
              aria-controls={`${baseId}-panel-${item.value}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => {
                selectAt(index);
              }}
              onKeyDown={(event) => {
                handleKeyDown(event, index);
              }}
              className={cx(
                '-mb-px border-b-2 px-4 py-2 text-sm font-medium',
                isSelected
                  ? 'border-pilot-700 text-pilot-800'
                  : 'border-transparent text-ink-600 hover:border-ink-300 hover:text-ink-900',
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>
      {items.map((item, index) => {
        const isSelected = index === selectedIndex;
        return (
          <div
            key={item.value}
            role="tabpanel"
            id={`${baseId}-panel-${item.value}`}
            aria-labelledby={`${baseId}-tab-${item.value}`}
            tabIndex={0}
            hidden={!isSelected}
            className="pt-4"
          >
            {isSelected && item.panel}
          </div>
        );
      })}
    </div>
  );
}

function nextIndex(key: string, index: number, count: number): number | null {
  switch (key) {
    case 'ArrowRight':
      return (index + 1) % count;
    case 'ArrowLeft':
      return (index - 1 + count) % count;
    case 'Home':
      return 0;
    case 'End':
      return count - 1;
    default:
      return null;
  }
}
