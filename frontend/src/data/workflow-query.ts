import type { AutoQuery, ResultsQuery } from './api';

export const DEFAULT_PAGE_LIMIT = 50;
const MAX_PAGE_LIMIT = 200;

function pageNumber(value: string | null, fallback: number, minimum: number, maximum?: number): number {
  if (value === null || value.trim() === '') return fallback;
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  const bounded = Math.max(minimum, parsed);
  return maximum === undefined ? bounded : Math.min(maximum, bounded);
}

function optional(params: URLSearchParams, key: string): string | undefined {
  const value = params.get(key)?.trim();
  return value ? value : undefined;
}

export function autoQueryFromSearch(params: URLSearchParams): AutoQuery {
  return {
    limit: pageNumber(params.get('limit'), DEFAULT_PAGE_LIMIT, 1, MAX_PAGE_LIMIT),
    offset: pageNumber(params.get('offset'), 0, 0),
    league: optional(params, 'league'),
    stat: optional(params, 'stat'),
    period: optional(params, 'period'),
    scope: optional(params, 'scope'),
    direction: optional(params, 'direction'),
    model: optional(params, 'model'),
    policy: optional(params, 'policy'),
  };
}

export function resultsQueryFromSearch(params: URLSearchParams): ResultsQuery {
  return {
    limit: pageNumber(params.get('limit'), DEFAULT_PAGE_LIMIT, 1, MAX_PAGE_LIMIT),
    offset: pageNumber(params.get('offset'), 0, 0),
    status: optional(params, 'status'),
    league: optional(params, 'league'),
    stat: optional(params, 'stat'),
    period: optional(params, 'period'),
    scope: optional(params, 'scope'),
    direction: optional(params, 'direction'),
  };
}

export function patchSearchParams(
  current: URLSearchParams,
  patch: Record<string, string | number | undefined>,
  options: { resetOffset?: boolean } = {},
): URLSearchParams {
  const next = new URLSearchParams(current);
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined || value === '') next.delete(key);
    else next.set(key, String(value));
  }
  if (options.resetOffset) next.delete('offset');
  return next;
}
