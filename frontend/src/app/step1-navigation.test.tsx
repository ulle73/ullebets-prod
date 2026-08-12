import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const match = {
  matchKey: 'm1', sourceMatchId: 1, sourceDate: '2026-08-13', startTime: '2026-08-13T18:00:00Z',
  leagueKey: 'league-a', leagueName: 'League A', homeTeamKey: 'home', awayTeamKey: 'away',
  homeTeamName: 'Home FC', awayTeamName: 'Away FC', statusType: 'notstarted', homeScore: null, awayScore: null,
};
const dashboard = {
  selectedDate: '2026-08-13', timezone: 'Europe/Stockholm', generatedAt: '2026-08-12T20:30:00Z', matchupSource: 'persisted',
  matches: [match],
  matchups: [{
    entryKey: 'row-1', snapshotDate: '2026-08-13', matchKey: 'm1', leagueKey: 'league-a', leagueName: 'League A',
    homeTeamKey: 'home', awayTeamKey: 'away', homeTeamName: 'Home FC', awayTeamName: 'Away FC',
    statKey: 'fouls', statLabel: 'Fouls', period: 'ALL', periodLabel: 'Hela matchen', scope: 'away', condition: 'OVER',
    score: 73.4, rankPosition: 1, isTop50: true, marketBias: null, leagueBaseline: 12.6,
  }],
};
const league = {
  league: { leagueKey: 'league-a', leagueName: 'League A', country: 'SE', seasonId: 2026, capturedAt: '2026-08-12T18:00:00Z' },
  teams: [{ teamKey: 'home', leagueKey: 'league-a', teamName: 'Home FC', teamImageUrl: null, optaRank: 22, optaRating: 81.2, capturedAt: '2026-08-12T18:00:00Z' }],
  ranking: null,
  matches: [match],
};
const auto = {
  summary: { total: 1, valid: 1, excluded: 0 }, page: { limit: 50, offset: 0, hasMore: false },
  selections: [{
    selectionKey: 's1', matchKey: 'm1', leagueKey: 'league-a', leagueName: 'League A', homeTeamKey: 'home', awayTeamKey: 'away',
    homeTeamName: 'Home FC', awayTeamName: 'Away FC', statKey: 'fouls', period: 'ALL', scope: 'away', direction: 'over',
    lineValue: 12.5, selectedOdds: 1.9, predictedWinProbability: 0.6, expectedRoiUnits: 0.14, modelId: 'v6',
    modelStatus: 'forward_test_only', policyId: 'policy-1', matchStartTime: '2026-08-13T18:00:00Z',
    validForForwardEvaluation: true, invalidForModel: false,
  }],
};
const results = {
  summary: { rows: 1, settled: 1, wins: 1, losses: 0, pushes: 0, excluded: 0 }, page: { limit: 50, offset: 0, hasMore: false },
  rows: [{
    resultLoopKey: 'r1', predictionKey: 'p1', selectionKey: 's1', matchKey: 'm1', leagueKey: 'league-a', leagueName: 'League A',
    homeTeamKey: 'home', awayTeamKey: 'away', homeTeamName: 'Home FC', awayTeamName: 'Away FC', statKey: 'fouls', period: 'ALL',
    scope: 'away', direction: 'over', lineValue: 12.5, savedOdds: 1.9, settlementStatus: 'settled', settlementResult: 'win',
    actualValue: 14, win: true, roiUnits: 0.9, pnlUnits: 0.9, validForPerformance: true, resultLoopStatus: 'settled',
    statusReason: 'settled', closingOdds: 1.8, closingQuality: 't10', officialClv: true, clvStatus: 'available', clvPct: 5.5,
    matchStartTime: '2026-08-13T18:00:00Z',
  }],
};

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.toString();
  return input.url;
}

describe('step 1 entity navigation', () => {
  it('renders a real league route backed by the league endpoint', async () => {
    renderApp('/liga/league-a', { '/api/v1/dashboard': dashboard, '/api/v1/leagues/league-a': league });
    expect(await screen.findByRole('heading', { name: 'League A' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Home FC' })).toHaveAttribute('href', '/lag/home');
    expect(screen.getByRole('link', { name: /Home FC.*Away FC/ })).toHaveAttribute('href', '/matcher/m1');
  });

  it('shows a real not-found route instead of redirecting broken URLs', async () => {
    renderApp('/detta-finns-inte', { '/api/v1/dashboard': dashboard });
    expect(await screen.findByRole('heading', { name: 'Sidan kunde inte hittas' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Till översikten' })).toHaveAttribute('href', '/oversikt');
  });

  it('links matchup league, both teams and match', async () => {
    renderApp('/oversikt?date=2026-08-13', { '/api/v1/dashboard': dashboard });
    await screen.findByText('73,4');
    expect(screen.getByRole('link', { name: 'League A' })).toHaveAttribute('href', '/liga/league-a');
    expect(screen.getByRole('link', { name: 'Home FC' })).toHaveAttribute('href', '/lag/home');
    expect(screen.getByRole('link', { name: 'Away FC' })).toHaveAttribute('href', '/lag/away');
    expect(screen.getByRole('link', { name: 'Matchdetalj' })).toHaveAttribute('href', '/matcher/m1');
  });

  it('links auto rows to league, teams and match', async () => {
    renderApp('/auto', { '/api/v1/dashboard': dashboard, '/api/v1/auto': auto });
    await screen.findByRole('heading', { name: 'Auto' });
    expect(screen.getByRole('link', { name: 'League A' })).toHaveAttribute('href', '/liga/league-a');
    expect(screen.getByRole('link', { name: 'Home FC' })).toHaveAttribute('href', '/lag/home');
    expect(screen.getByRole('link', { name: 'Away FC' })).toHaveAttribute('href', '/lag/away');
    expect(screen.getByRole('link', { name: /Home FC.*Away FC/ })).toHaveAttribute('href', '/matcher/m1');
  });

  it('links result rows to league, teams and match using typed result data', async () => {
    renderApp('/resultatloop', { '/api/v1/dashboard': dashboard, '/api/v1/results': results });
    await screen.findByRole('heading', { name: 'Resultatloop' });
    expect(screen.getByRole('link', { name: 'League A' })).toHaveAttribute('href', '/liga/league-a');
    expect(screen.getByRole('link', { name: 'Home FC' })).toHaveAttribute('href', '/lag/home');
    expect(screen.getByRole('link', { name: 'Away FC' })).toHaveAttribute('href', '/lag/away');
    expect(screen.getByRole('link', { name: /Home FC.*Away FC/ })).toHaveAttribute('href', '/matcher/m1');
  });

  it('resolves saved match ids independently of the current dashboard date', async () => {
    window.localStorage.setItem('ullebets:watchlist:v1', JSON.stringify([{ kind: 'match', id: 'saved-match' }]));
    renderApp('/watchlist', {
      '/api/v1/dashboard': { ...dashboard, matches: [] },
      '/api/v1/matches': { matches: [{ ...match, matchKey: 'saved-match', homeTeamName: 'Saved Home', awayTeamName: 'Saved Away' }] },
    });
    expect(await screen.findByRole('link', { name: /Saved Home.*Saved Away/ })).toHaveAttribute('href', '/matcher/saved-match');
  });

  it('lets the server resolve product day when no explicit date was selected', async () => {
    const { fetchMock } = renderApp('/oversikt', { '/api/v1/dashboard': dashboard });
    await screen.findByText('73,4');
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([input]) => requestUrl(input));
      expect(calls).toContain('/api/v1/dashboard');
      expect(calls.some((call) => call.startsWith('/api/v1/dashboard?date='))).toBe(false);
    });
  });
});
