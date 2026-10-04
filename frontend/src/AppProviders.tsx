import { QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import type { ReactNode } from 'react';

import { ToastProvider } from './components/ui/toast/ToastProvider';
import { createQueryClient } from './lib/queryClient';

interface AppProvidersProps {
  children: ReactNode;
}

/** App-wide providers except the router, so tests can wrap them in a `MemoryRouter`. */
export function AppProviders({ children }: AppProvidersProps) {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}
