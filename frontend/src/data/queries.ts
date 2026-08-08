import { useQuery } from '@tanstack/react-query';
import { fetchAuto, fetchDashboard, fetchMatchDetail, fetchModel, fetchResults, fetchSystem, fetchTeam } from './api';

export function useDashboard(date?: string) {
  return useQuery({
    queryKey: ['dashboard', date ?? 'latest'],
    queryFn: ({ signal }) => fetchDashboard(date, signal),
    staleTime: 15_000,
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

export function useAuto() {
  return useQuery({ queryKey: ['auto'], queryFn: ({ signal }) => fetchAuto(signal), staleTime: 15_000 });
}

export function useResults() {
  return useQuery({ queryKey: ['results'], queryFn: ({ signal }) => fetchResults(signal), staleTime: 30_000 });
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
