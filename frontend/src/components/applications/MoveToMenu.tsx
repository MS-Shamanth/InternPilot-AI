import { useEffect, useId, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { cx } from '../../lib/classNames';
import type { ApplicationStatus } from '../../types/api';
import { buttonClasses } from '../ui/buttonStyles';

interface MoveToMenuProps {
  /** Allowed targets only (from `/applications/meta`), in display order. */
  targets: readonly ApplicationStatus[];
  /** Names the card in the button's accessible name, e.g. "Move to… Frontend Intern". */
  itemLabel: string;
  disabled?: boolean;
  onSelect: (status: ApplicationStatus) => void;
}

/**
 * WAI-ARIA menu button listing the statuses a card may move to (R5.11, R14.4).
 *
 * Enter/Space/ArrowDown open it on the first item, ArrowUp on the last; inside, ArrowUp/Down
 * wrap, Home/End jump, Enter/Space choose, Escape closes and Tab leaves. Focus returns to the
 * button whenever the menu closes from the keyboard or a choice.
 */
export function MoveToMenu({ targets, itemLabel, disabled = false, onSelect }: MoveToMenuProps) {
  const buttonId = useId();
  const menuId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const isOpen = activeIndex !== null;
  const unavailable = disabled || targets.length === 0;

  useEffect(() => {
    if (activeIndex !== null) {
      itemRefs.current[activeIndex]?.focus();
    }
  }, [activeIndex]);

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }
    function handlePointerDown(event: MouseEvent) {
      if (event.target instanceof Node && containerRef.current?.contains(event.target) !== true) {
        setActiveIndex(null);
      }
    }
    document.addEventListener('mousedown', handlePointerDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
    };
  }, [isOpen]);

  function open(index: number) {
    if (!unavailable) {
      setActiveIndex(index);
    }
  }

  function close() {
    setActiveIndex(null);
    buttonRef.current?.focus();
  }

  function choose(status: ApplicationStatus) {
    close();
    onSelect(status);
  }

  function handleButtonKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      open(0);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      open(targets.length - 1);
    }
  }

  function handleMenuKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    if (activeIndex === null) {
      return;
    }
    const last = targets.length - 1;
    const moves: Record<string, number> = {
      ArrowDown: activeIndex === last ? 0 : activeIndex + 1,
      ArrowUp: activeIndex === 0 ? last : activeIndex - 1,
      Home: 0,
      End: last,
    };
    const next = moves[event.key];
    if (next !== undefined) {
      event.preventDefault();
      setActiveIndex(next);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      close();
    } else if (event.key === 'Tab') {
      setActiveIndex(null);
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        id={buttonId}
        type="button"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={isOpen ? menuId : undefined}
        disabled={unavailable}
        title={targets.length === 0 ? 'No moves are allowed from this status' : undefined}
        className={buttonClasses({ variant: 'secondary', size: 'sm' })}
        onClick={() => {
          if (isOpen) {
            setActiveIndex(null);
          } else {
            open(0);
          }
        }}
        onKeyDown={handleButtonKeyDown}
      >
        Move to…<span className="sr-only"> {itemLabel}</span>
      </button>
      {isOpen && (
        <ul
          id={menuId}
          role="menu"
          aria-labelledby={buttonId}
          tabIndex={-1}
          className="absolute left-0 z-20 mt-1 min-w-40 rounded border border-ink-200 bg-white py-1 shadow-lg"
          onKeyDown={handleMenuKeyDown}
        >
          {targets.map((status, index) => (
            <li key={status} role="none">
              <button
                ref={(element) => {
                  itemRefs.current[index] = element;
                }}
                type="button"
                role="menuitem"
                tabIndex={index === activeIndex ? 0 : -1}
                className={cx(
                  'block w-full px-3 py-1.5 text-left text-sm text-ink-800 hover:bg-pilot-50',
                  'focus:bg-pilot-50 focus:text-pilot-800',
                )}
                onClick={() => {
                  choose(status);
                }}
              >
                {status}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
