import type { FormulaPerformanceQuery } from './api';


const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;

function optional(params: URLSearchParams, key: string): string | undefined {
  const value = params.get(key)?.trim();
  return value || undefined;
}

function integer(params: URLSearchParams, key: string, fallback: number, minimum: number, maximum: number): number {
  const value = Number.parseInt(params.get(key) ?? '', 10);
  return Number.isFinite(value) ? Math.min(maximum, Math.max(minimum, value)) : fallback;
}

export function formulaPerformanceQueryFromSearch(params: URLSearchParams): FormulaPerformanceQuery {
  const query: FormulaPerformanceQuery = {
    limit: integer(params, 'limit', DEFAULT_LIMIT, 1, MAX_LIMIT),
    offset: integer(params, 'offset', 0, 0, Number.MAX_SAFE_INTEGER),
    mode: params.get('mode') === 'all_scores' ? 'all_scores' : 'positive_ev',
  };
  for (const key of ['formula', 'family', 'league', 'stat', 'period', 'scope', 'direction', 'checkpoint', 'status'] as const) {
    const value = optional(params, key);
    if (value) query[key] = value;
  }
  return query;
}
