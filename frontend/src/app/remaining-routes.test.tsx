import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const dashboard = { selectedDate: '2026-08-13', timezone: 'Europe/Stockholm', generatedAt: '2026-08-12T20:00:00Z', matchupSource: 'missing', matches: [], matchups: [] };

describe('complete Style-1 route surface', () => {
  it('renders Auto from registered forward data', async () => {
    renderApp('/auto', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/auto': {
        summary: { total: 1, valid: 1, excluded: 0 },
        page: { limit: 50, offset: 0, hasMore: false },
        selections: [{
          selectionKey: 's1', predictionKey: 'p1', matchKey: 'm1', leagueKey: 'league', leagueName: 'League',
          homeTeamKey: 'a', awayTeamKey: 'b', homeTeamName: 'A', awayTeamName: 'B', statKey: 'cornerKicks', period: 'ALL', scope: 'away', direction: 'OVER',
          lineValue: 4.5, selectedOdds: 1.91, predictedWinProbability: 0.61, expectedRoiUnits: 0.09, modelId: 'model-live', modelStatus: 'forward_test_only',
          policyId: 'policy-live', policyStatus: 'shadow', snapshotKey: 'snap', offerKey: 'offer', oddsSnapshotTime: null, predictionCreatedAt: null,
          matchStartTime: null, validForForwardEvaluation: true, invalidForModel: false,
        }],
      },
    });
    expect(await screen.findByRole('heading', { name: 'Auto' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'A' })).toHaveAttribute('href', '/lag/a');
    expect(screen.getByText('1,91')).toBeInTheDocument();
  });

  it('renders Resultatloop from typed forward result data', async () => {
    renderApp('/resultatloop', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/results': {
        summary: { rows: 9, settled: 7, wins: 4, losses: 3, pushes: 0, excluded: 2 },
        page: { limit: 50, offset: 0, hasMore: false },
        rows: [],
      },
    });
    expect(await screen.findByRole('heading', { name: 'Resultatloop' })).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('renders a typed team profile returned by the read API', async () => {
    renderApp('/lag/team-key', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/teams/team-key': {
        team: { teamKey: 'team-key', leagueKey: 'league-key', teamId: 1, teamName: 'Live Team', teamImageUrl: null, optaId: null, optaRank: null, optaRating: null, capturedAt: null },
        league: { leagueKey: 'league-key', leagueName: 'Live League', leagueId: 1, country: null, seasonId: 2026, categoryId: null, groupId: null, capturedAt: null },
        contexts: {
          home: { profileKey: 'profile', profileDate: 'current', generatedAt: null, matchType: 'home', leagueTeamCount: 18, savedAt: null, games: [], statistics: { for: { fouls: { ALL: { value: 10.2, rank: 3 } } }, leagueAverage: { for: { fouls: { ALL: { value: 11.1 } } } } }, specials: {}, behaviour: null },
          away: null,
        },
        matches: [],
      },
    });
    expect(await screen.findByRole('heading', { name: 'Live Team' })).toBeInTheDocument();
    expect(screen.getAllByText('10,2').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'Öppna ligan' })).toHaveAttribute('href', '/liga/league-key');
  });

  it('renders model counters returned by V2', async () => {
    renderApp('/modell', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/model': { modelIds: ['model-live'], policyIds: ['policy-live'], scoreCount: 12, forwardSelectionCount: 3, settledForwardCount: 2, officialClvCount: 1 },
    });
    expect(await screen.findByRole('heading', { name: 'Modell & proof' })).toBeInTheDocument();
    expect(screen.getByText('model-live')).toBeInTheDocument();
    expect(screen.getByText('policy-live')).toBeInTheDocument();
  });

  it('renders system jobs returned by V2', async () => {
    renderApp('/systemstatus', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/system': { jobs: [{ run_id: 'r1', job_name: 'live-job', source_workflow: 'workflow.yml', status: 'succeeded', started_at: '2026-08-09T00:00:00Z', finished_at: '2026-08-09T00:01:00Z' }], health: [], audits: [] },
    });
    expect(await screen.findByRole('heading', { name: 'Systemstatus' })).toBeInTheDocument();
    expect(screen.getByText('live-job')).toBeInTheDocument();
  });
});
