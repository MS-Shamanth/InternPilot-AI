import { useEffect, useId, useRef } from 'react';
import type { ReactNode, RefObject } from 'react';
import { createPortal } from 'react-dom';

import { cx } from '../../lib/classNames';
import { IconButton } from './IconButton';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: ReactNode;
  /** Action row (e.g. Cancel / Save buttons), right-aligned below the body. */
  footer?: ReactNode;
  /** Clicking the dimmed backdrop closes the dialog unless this is false. */
  closeOnBackdropClick?: boolean;
  /** Element to focus on open; defaults to the dialog itself so its title is announced. */
  initialFocusRef?: RefObject<HTMLElement>;
  size?: 'md' | 'lg';
}

/**
 * Modal dialog rendered in a portal on `document.body` (R14.4): focus moves inside on open,
 * Tab/Shift+Tab are trapped, Escape closes, body scroll is locked, and focus returns to the
 * previously focused element (normally the trigger) on close.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  closeOnBackdropClick = true,
  initialFocusRef,
  size = 'md',
}: DialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const panel = panelRef.current;
    if (!open || panel === null) {
      return undefined;
    }
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    (initialFocusRef?.current ?? panel).focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onCloseRef.current();
      } else if (event.key === 'Tab' && panel !== null) {
        trapTab(event, panel);
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      if (previouslyFocused?.isConnected === true) {
        previouslyFocused.focus();
      }
    };
  }, [open, initialFocusRef]);

  if (!open) {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div
        aria-hidden="true"
        data-testid="dialog-backdrop"
        className="absolute inset-0 bg-ink-900/50"
        onClick={() => {
          if (closeOnBackdropClick) {
            onCloseRef.current();
          }
        }}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description === undefined ? undefined : descriptionId}
        tabIndex={-1}
        className={cx(
          'relative flex max-h-[90vh] w-full flex-col rounded bg-white shadow-xl focus:outline-none',
          size === 'lg' ? 'max-w-2xl' : 'max-w-lg',
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-ink-200 px-6 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-lg font-semibold text-ink-900">
              {title}
            </h2>
            {description !== undefined && (
              <p id={descriptionId} className="mt-1 text-sm text-ink-600">
                {description}
              </p>
            )}
          </div>
          <IconButton aria-label="Close dialog" size="sm" icon="×" onClick={onClose} />
        </div>
        {children !== undefined && <div className="overflow-y-auto px-6 py-4">{children}</div>}
        {footer !== undefined && (
          <div className="flex justify-end gap-2 border-t border-ink-200 px-6 py-4">{footer}</div>
        )}
      </div>
    </div>,
    document.body,
  );
}

/** Keeps Tab/Shift+Tab cycling through the panel's focusable elements. */
function trapTab(event: KeyboardEvent, panel: HTMLElement) {
  const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (first === undefined || last === undefined) {
    event.preventDefault();
    panel.focus();
    return;
  }
  const active = document.activeElement;
  const outside = active === panel || !(active instanceof Node) || !panel.contains(active);
  if (event.shiftKey && (outside || active === first)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (outside || active === last)) {
    event.preventDefault();
    first.focus();
  }
}
