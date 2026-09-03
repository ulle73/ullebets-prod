import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const dashboard = {
  selectedDate: '2026-08-09',
  timezone: 'Europe/Stockholm',
  generatedAt: '2026-08-09T08:00:00Z',
  matchupSource: 'persisted',
  matches: [{
    matchKey: 'sofascore:123', sourceMatchId: 123, sourceDate: '2026-08-09', startTime: '2026-08-09T18:00:00Z',
    leagueKey: 'test', leagueName: 'Test League', homeTeamKey: 'home', awayTeamKey: 'away', homeTeamName: 'Home FC', awayTeamName: 'Away FC', statusType: 'notstarted',
    state: 'upcoming', homeScore: null, awayScore: null, resultFetchedAt: null,
  }],
  matchups: [{
    entryKey: 'row-1', snapshotDate: '2026-08-09', matchKey: 'sofascore:123', leagueKey: 'test', leagueName: 'Test League',
    homeTeamKey: 'home', awayTeamKey: 'away', homeTeamName: 'Home FC', awayTeamName: 'Away FC', statKey: 'fouls', statLabel: 'Fouls', period: 'ALL', periodLabel: 'Hela matchen',
    scope: 'away', condition: 'OVER', score: 73.4, rankPosition: 1, isTop50: true, marketBias: null, leagueBaseline: 12.6,
  }],
};

describe('Ullebets application shell', () => {
  it('shows exactly the four primary destinations', () => {
    renderApp('/oversikt', { '/api/v1/dashboard': dashboard });
    const nav = screen.getByRole('navigation', { name: 'Huvudnavigation' });
    expect(Array.from(nav.querySelectorAll('a')).map((link) => link.textContent)).toEqual(['Översikt', 'Spel & resultat', 'Watchlist', 'Historik']);
  });

  it('renders matches and matchup score returned by the read API', async () => {
    renderApp('/oversikt', { '/api/v1/dashboard': dashboard });
    expect((await screen.findAllByText('Home FC')).length).toBeGreaterThan(0);
    expect(await screen.findByText('73,4')).toBeInTheDocument();
    expect(await screen.findByText('Historisk linjeprofil')).toBeInTheDocument();
    expect(screen.queryByText(/Bet365/i)).not.toBeInTheDocument();
  });

  it('loads a lazy route within the application shell', async () => {
    renderApp('/modell', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/model': { modelIds: [], policyIds: [], scoreCount: 0, forwardSelectionCount: 0, settledForwardCount: 0, officialClvCount: 0 },
    });

    expect(await screen.findByRole('heading', { name: 'Modell & proof' }, { timeout: 5_000 })).toBeInTheDocument();
  });
});
