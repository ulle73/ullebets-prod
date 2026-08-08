import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { App } from '../app/App';

export function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } });
}

export function renderApp(route: string, responses: Record<string, unknown> = {}) {
  const dashboardFallback = { selectedDate: null, matches: [], matchups: [] };
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const raw = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const path = raw.startsWith('http') ? new URL(raw).pathname : raw.split('?')[0]!;
    const payload = path === '/api/v1/dashboard' ? (responses[path] ?? dashboardFallback) : responses[path];
    return Promise.resolve(payload === undefined ? jsonResponse({ error: 'not_found' }, 404) : jsonResponse(payload));
  });
  vi.stubGlobal('fetch', fetchMock);

  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...view, fetchMock, queryClient };
}

export function withProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
