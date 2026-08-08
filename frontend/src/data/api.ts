import type {
  AutoResponse,
  DashboardResponse,
  MatchDetailResponse,
  ModelResponse,
  ResultsResponse,
  SystemResponse,
  TeamResponse,
} from '../domain/types';

type QueryValue = string | number | boolean | null | undefined;

export function buildApiUrl(path: string, query: Record<string, QueryValue> = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    params.set(key, String(value));
  }
  const suffix = params.toString();
  return `/api/v1${path}${suffix ? `?${suffix}` : ''}`;
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Read API returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchDashboard(date?: string, signal?: AbortSignal): Promise<DashboardResponse> {
  return getJson(buildApiUrl('/dashboard', { date }), signal);
}

export function fetchMatchDetail(matchKey: string, signal?: AbortSignal): Promise<MatchDetailResponse> {
  return getJson(buildApiUrl(`/matches/${encodeURIComponent(matchKey)}`), signal);
}

export function fetchAuto(signal?: AbortSignal): Promise<AutoResponse> {
  return getJson(buildApiUrl('/auto'), signal);
}

export function fetchResults(signal?: AbortSignal): Promise<ResultsResponse> {
  return getJson(buildApiUrl('/results'), signal);
}

export function fetchTeam(teamKey: string, signal?: AbortSignal): Promise<TeamResponse> {
  return getJson(buildApiUrl(`/teams/${encodeURIComponent(teamKey)}`), signal);
}

export function fetchModel(signal?: AbortSignal): Promise<ModelResponse> {
  return getJson(buildApiUrl('/model'), signal);
}

export function fetchSystem(signal?: AbortSignal): Promise<SystemResponse> {
  return getJson(buildApiUrl('/system'), signal);
}
