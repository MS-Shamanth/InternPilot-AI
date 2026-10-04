import { createContext } from 'react';

export type ToastVariant = 'success' | 'error' | 'info';

export interface Toast {
  id: number;
  variant: ToastVariant;
  message: string;
}

export interface ToastApi {
  success: (message: string) => void;
  info: (message: string) => void;
  error: (message: string) => void;
  /** Error toast from any thrown value; an `ApiError` shows its envelope message. */
  fromError: (error: unknown) => void;
  dismiss: (id: number) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);
