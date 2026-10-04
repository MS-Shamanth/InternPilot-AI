import { QueryClientProvider } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { createQueryClient } from '../../src/lib/queryClient';

interface WrapperProps {
  children: ReactNode;
}

/** The app's real client, with zero retry delay so retry tests do not wait on backoff. */
export function createTestQueryClient(): QueryClient {
  const queryClient = createQueryClient();
  const defaults = queryClient.getDefaultOptions();
  queryClient.setDefaultOptions({
    ...defaults,
    queries: { ...defaults.queries, retryDelay: 0 },
  });
  return queryClient;
}

export function createWrapper(queryClient: QueryClient): (props: WrapperProps) => ReactNode {
  return function Wrapper({ children }: WrapperProps) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}
