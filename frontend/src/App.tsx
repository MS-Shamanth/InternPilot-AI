import { BrowserRouter } from 'react-router-dom';

import { AppProviders } from './AppProviders';
import { AppRoutes } from './AppRoutes';
import { ROUTER_FUTURE_FLAGS } from './lib/router';

export default function App() {
  return (
    <BrowserRouter future={ROUTER_FUTURE_FLAGS}>
      <AppProviders>
        <AppRoutes />
      </AppProviders>
    </BrowserRouter>
  );
}
