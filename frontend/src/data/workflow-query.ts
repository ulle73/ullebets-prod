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
  const query: AutoQuery = {
    limit: pageNumber(params.get('limit'), DEFAULT_PAGE_LIMIT, 1, MAX_PAGE_LIMIT),
    offset: pageNumber(params.get('offset'), 0, 0),
  };
  const league = optional(params, 'league');
  const stat = optional(params, 'stat');
  const period = optional(params, 'period');
  const scope = optional(params, 'scope');
  const direction = optional(params, 'direction');
  const model = optional(params, 'model');
  const policy = optional(params, 'policy');
  if (league) query.league = league;
  if (stat) query.stat = stat;
  if (period) query.period = period;
  if (scope) query.scope = scope;
  if (direction) query.direction = direction;
  if (model) query.model = model;
  if (policy) query.policy = policy;
  return query;
}

export function resultsQueryFromSearch(params: URLSearchParams): ResultsQuery {
  const query: ResultsQuery = {
    limit: pageNumber(params.get('limit'), DEFAULT_PAGE_LIMIT, 1, MAX_PAGE_LIMIT),
    offset: pageNumber(params.get('offset'), 0, 0),
  };
  const status = optional(params, 'status');
  const league = optional(params, 'league');
  const stat = optional(params, 'stat');
  const period = optional(params, 'period');
  const scope = optional(params, 'scope');
  const direction = optional(params, 'direction');
  if (status) query.status = status;
  if (league) query.league = league;
  if (stat) query.stat = stat;
  if (period) query.period = period;
  if (scope) query.scope = scope;
  if (direction) query.direction = direction;
  return query;
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
