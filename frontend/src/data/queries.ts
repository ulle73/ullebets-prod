import { useQuery } from '@tanstack/react-query';
import { fetchAuto, fetchDashboard, fetchMatchDetail, fetchModel, fetchResults, fetchSystem, fetchTeam } from './api';

export function localDateKey(now = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function useDashboard(date?: string) {
  const selectedDate = date || localDateKey();
  return useQuery({
    queryKey: ['dashboard', selectedDate],
    queryFn: ({ signal }) => fetchDashboard(selectedDate, signal),
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
