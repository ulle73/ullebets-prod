import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const dashboard = { selectedDate: null, matches: [], matchups: [] };

describe('complete Style-1 route surface', () => {
  it('renders Auto from forward_bets read data', async () => {
    renderApp('/auto', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/auto': { count: 1, selections: [{ selectionKey: 's1', matchKey: 'm1', homeTeamName: 'A', awayTeamName: 'B', leagueName: 'League', statKey: 'cornerKicks', period: 'ALL', scope: 'away', direction: 'OVER', lineValue: 4.5, selectedOdds: 1.91, predictedWinProbability: 0.61, expectedRoiUnits: 0.09, modelId: 'model-live', modelStatus: 'forward_test_only', policyId: 'policy-live', matchStartTime: null, validForForwardEvaluation: true, invalidForModel: false }] },
    });
    expect(await screen.findByRole('heading', { name: 'Auto' })).toBeInTheDocument();
    expect(await screen.findByText('A – B')).toBeInTheDocument();
    expect(screen.getByText('1,91')).toBeInTheDocument();
  });

  it('renders Resultatloop from forward_results read data', async () => {
    renderApp('/resultatloop', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/results': { summary: { rows: 9, settled: 7, wins: 4, losses: 3, excluded: 2 }, rows: [] },
    });
    expect(await screen.findByRole('heading', { name: 'Resultatloop' })).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('renders a team profile returned by V2', async () => {
    renderApp('/lag/team-key', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/teams/team-key': { teamKey: 'team-key', profiles: [{ match_type: 'home', profile_date: '2026-08-09', meta: { lagnamn: 'Live Team', leagueName: 'Live League' }, statistics: { for: { fouls: { ALL: { value: 10.2, rank: 3 } } }, leagueAverage: { for: { fouls: { ALL: { value: 11.1 } } } } } }] },
    });
    expect(await screen.findByRole('heading', { name: 'Live Team' })).toBeInTheDocument();
    expect(screen.getByText('10.2')).toBeInTheDocument();
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
