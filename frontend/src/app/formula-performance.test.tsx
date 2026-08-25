import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';


const dashboard = {
  selectedDate: '2026-08-23',
  timezone: 'Europe/Stockholm',
  generatedAt: '2026-08-23T10:00:00Z',
  matchupSource: 'missing',
  matches: [],
  matchups: [],
};

const formulaPerformance = {
  generatedAt: '2026-08-23T10:00:00Z',
  mode: 'positive_ev',
  summary: {
    formulaId: null, formulaLabel: null, formulaFamily: null,
    observations: 80, shadowBets: 80, settled: 40, settledBets: 40,
    uniqueMatches: 30, uniqueSettledMatches: 25,
    wins: 25, losses: 15, pushes: 0,
    stakeUnits: 40, pnlUnits: 5, roiPct: 12.5,
    averagePredictedProbabilityPct: 57.2, averageEvPct: 8.1,
    calibrationObservations: 40, brierScore: 0.2214, logLoss: 0.6341,
    officialClvObservations: 32, averageClvPct: 2.4,
    beatClosingLine: 19, clvBeatRatePct: 59.4, evidenceLevel: 'growing',
  },
  facets: {
    formulas: [{ value: 'js:evPct', label: 'Basformel', count: 80 }],
    families: [{ value: 'heuristic', label: 'heuristic', count: 80 }],
    stats: [{ value: 'cornerKicks', label: 'cornerKicks', count: 80 }],
    scopes: [{ value: 'total', label: 'total', count: 80 }],
    periods: [{ value: 'ALL', label: 'ALL', count: 80 }],
    directions: [{ value: 'over', label: 'over', count: 80 }],
    leagues: [{ value: 'premier-league', label: 'Premier League', count: 80 }],
    checkpoints: [{ value: 'T_MINUS_2H', label: 'T_MINUS_2H', count: 80 }],
  },
  page: { limit: 50, offset: 0, hasMore: false },
  groups: [{
    formulaId: 'js:evPct', formulaLabel: 'Basformel', formulaFamily: 'heuristic',
    observations: 80, shadowBets: 80, settled: 40, settledBets: 40,
    uniqueMatches: 30, uniqueSettledMatches: 25,
    wins: 25, losses: 15, pushes: 0,
    stakeUnits: 40, pnlUnits: 5, roiPct: 12.5,
    averagePredictedProbabilityPct: 57.2, averageEvPct: 8.1,
    calibrationObservations: 40, brierScore: 0.2214, logLoss: 0.6341,
    officialClvObservations: 32, averageClvPct: 2.4,
    beatClosingLine: 19, clvBeatRatePct: 59.4, evidenceLevel: 'growing',
  }],
};

describe('formula performance', () => {
  it('shows the simple comparison and sends URL-backed stat filters', async () => {
    const { fetchMock } = renderApp('/modell', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/model': {
        modelIds: ['v6'], policyIds: ['policy-v6'], modelStatuses: ['shadow_only'],
        policyStatuses: ['shadow'], scoreCount: 80, forwardSelectionCount: 10,
        settledForwardCount: 5, officialClvCount: 4,
      },
      '/api/v1/formula-performance': formulaPerformance,
    });

    expect(await screen.findByRole('heading', { name: 'Modelljämförelse' })).toBeVisible();
    expect((await screen.findAllByText('+12,5 %')).length).toBeGreaterThan(0);
    expect(screen.getByText('Växande underlag')).toBeVisible();
    expect(screen.getByText('25 matcher')).toBeVisible();
    expect(screen.getByText('Brier visar hur väl sannolikheterna är kalibrerade. Lägre är bättre.')).toBeVisible();

    await userEvent.selectOptions(screen.getByLabelText('Statistik'), 'cornerKicks');
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([input]) => (
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url
      ));
      expect(urls.some((url) => url.includes('/api/v1/formula-performance?') && url.includes('stat=cornerKicks'))).toBe(true);
    });
  });

  it('renders missing metrics as em dash instead of zero', async () => {
    const emptyMetric = structuredClone(formulaPerformance);
    emptyMetric.summary.roiPct = null as unknown as number;
    emptyMetric.summary.averageClvPct = null as unknown as number;
    emptyMetric.groups[0]!.roiPct = null as unknown as number;
    emptyMetric.groups[0]!.averageClvPct = null as unknown as number;
    renderApp('/modell', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/model': { modelIds: [], policyIds: [], modelStatuses: [], policyStatuses: [], scoreCount: 0, forwardSelectionCount: 0, settledForwardCount: 0, officialClvCount: 0 },
      '/api/v1/formula-performance': emptyMetric,
    });

    expect((await screen.findAllByText('—')).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('40 öppna 1u-spel väntar på rättning')).toBeVisible();
    expect(screen.getByText('Väntar på officiell T-10-closing')).toBeVisible();
  });
});
