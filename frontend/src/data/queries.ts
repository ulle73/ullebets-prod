import { useQuery } from '@tanstack/react-query';
import {
  fetchAuto,
  fetchDashboard,
  fetchLeague,
  fetchMatchDetail,
  fetchMatches,
  fetchModel,
  fetchResults,
  fetchSystem,
  fetchTeam,
  type AutoQuery,
  type ResultsQuery,
} from './api';

export function localDateKey(now = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function useDashboard(date?: string) {
  return useQuery({
    queryKey: ['dashboard', date ?? 'product-today'],
    queryFn: ({ signal }) => fetchDashboard(date, signal),
    staleTime: 15_000,
  });
}

export function useMatches(matchKeys: string[]) {
  return useQuery({
    queryKey: ['matches', matchKeys],
    queryFn: ({ signal }) => fetchMatches(matchKeys, signal),
    enabled: matchKeys.length > 0,
    staleTime: 30_000,
  });
}

export function useMatchDetail(matchKey?: string) {
  return useQuery({
    queryKey: ['match', matchKey],
    queryFn: ({ signal }) => fetchMatchDetail(matchKey!, signal),
    enabled: Boolean(matchKey),
    staleTime: 15_000,
  });
}

export function useLeague(leagueKey?: string) {
  return useQuery({
    queryKey: ['league', leagueKey],
    queryFn: ({ signal }) => fetchLeague(leagueKey!, signal),
    enabled: Boolean(leagueKey),
    staleTime: 60_000,
  });
}

export function useAuto(query: AutoQuery = {}) {
  return useQuery({
    queryKey: ['auto', query],
    queryFn: ({ signal }) => fetchAuto(query, signal),
    staleTime: 15_000,
  });
}

export function useResults(query: ResultsQuery = {}) {
  return useQuery({
    queryKey: ['results', query],
    queryFn: ({ signal }) => fetchResults(query, signal),
    staleTime: 30_000,
  });
}

export function useTeam(teamKey?: string) {
  return useQuery({
    queryKey: ['team', teamKey],
    queryFn: ({ signal }) => fetchTeam(teamKey!, signal),
    enabled: Boolean(teamKey),
    staleTime: 60_000,
  });
}

export function useModel() {
  return useQuery({ queryKey: ['model'], queryFn: ({ signal }) => fetchModel(signal), staleTime: 30_000 });
}

export function useSystemStatus() {
  return useQuery({ queryKey: ['system'], queryFn: ({ signal }) => fetchSystem(signal), staleTime: 15_000 });
}
