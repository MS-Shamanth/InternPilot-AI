import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { toastErrorMessage } from '../../../lib/toastMessages';
import { ToastContext } from './toastContext';
import type { Toast, ToastApi, ToastVariant } from './toastContext';

export const DEFAULT_TOAST_DURATION_MS = 5000;
export const DEFAULT_ERROR_TOAST_DURATION_MS = 10000;
export const DEFAULT_MAX_VISIBLE_TOASTS = 3;

interface ToastProviderProps {
  children: ReactNode;
  /** Auto-dismiss delay for success and info toasts. */
  durationMs?: number;
  /** Auto-dismiss delay for error toasts (longer, so the message can be read). */
  errorDurationMs?: number;
  /** Oldest toasts are dropped beyond this count. */
  maxVisible?: number;
}

const VARIANT_LABEL: Record<ToastVariant, string> = {
  success: 'Success',
  error: 'Error',
  info: 'Info',
};

const VARIANT_CLASSES: Record<ToastVariant, string> = {
  success: 'border-l-success-500',
  error: 'border-l-danger-500',
  info: 'border-l-pilot-500',
};

const LABEL_CLASSES: Record<ToastVariant, string> = {
  success: 'text-success-700',
  error: 'text-danger-700',
  info: 'text-pilot-700',
};

/** Holds the toast queue and renders the polite (status) and assertive (alert) live regions. */
export function ToastProvider({
  children,
  durationMs = DEFAULT_TOAST_DURATION_MS,
  errorDurationMs = DEFAULT_ERROR_TOAST_DURATION_MS,
  maxVisible = DEFAULT_MAX_VISIBLE_TOASTS,
}: ToastProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach(clearTimeout);
      pending.clear();
    };
  }, []);

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer !== undefined) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    (variant: ToastVariant, message: string) => {
      const id = nextId.current++;
      setToasts((current) => [...current, { id, variant, message }].slice(-maxVisible));
      const delay = variant === 'error' ? errorDurationMs : durationMs;
      timers.current.set(
        id,
        setTimeout(() => {
          dismiss(id);
        }, delay),
      );
    },
    [dismiss, durationMs, errorDurationMs, maxVisible],
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => {
        show('success', message);
      },
      info: (message) => {
        show('info', message);
      },
      error: (message) => {
        show('error', message);
      },
      fromError: (error) => {
        show('error', toastErrorMessage(error));
      },
      dismiss,
    }),
    [dismiss, show],
  );

  const errors = toasts.filter((toast) => toast.variant === 'error');
  const notices = toasts.filter((toast) => toast.variant !== 'error');

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:left-auto sm:w-96">
        <div role="alert" aria-live="assertive" className="flex w-full flex-col gap-2">
          {errors.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
          ))}
        </div>
        <div role="status" aria-live="polite" className="flex w-full flex-col gap-2">
          {notices.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
}

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: number) => void;
}

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 rounded border border-l-4 border-ink-200 bg-white p-3 shadow-md ${VARIANT_CLASSES[toast.variant]}`}
    >
      <p className="min-w-0 flex-1 text-sm text-ink-800">
        <span className={`font-semibold ${LABEL_CLASSES[toast.variant]}`}>
          {VARIANT_LABEL[toast.variant]}:
        </span>{' '}
        {toast.message}
      </p>
      <button
        type="button"
        onClick={() => {
          onDismiss(toast.id);
        }}
        className="shrink-0 rounded px-1 text-lg leading-none text-ink-600 hover:bg-ink-100 hover:text-ink-900"
        aria-label="Dismiss notification"
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  );
}
