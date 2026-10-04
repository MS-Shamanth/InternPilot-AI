import { useContext } from 'react';

import { ToastContext } from '../components/ui/toast/toastContext';
import type { ToastApi } from '../components/ui/toast/toastContext';

/** Show toasts for mutation outcomes (R14.3). Must be used inside `ToastProvider`. */
export function useToast(): ToastApi {
  const toast = useContext(ToastContext);
  if (toast === null) {
    throw new Error('useToast must be used inside <ToastProvider>.');
  }
  return toast;
}
