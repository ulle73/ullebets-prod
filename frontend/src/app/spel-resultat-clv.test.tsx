import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const dashboard = {
  selectedDate: '2026-08-13',
  timezone: 'Europe/Stockholm',
  generatedAt: '2026-08-12T20:00:00Z',
  matchupSource: 'missing',
  matches: [],
  matchups: [],
};

const selection = {
  selectionKey: 's1', predictionKey: 'p1', matchKey: 'm1', leagueKey: 'league-a', leagueName: 'League A',
  homeTeamKey: 'home', awayTeamKey: 'away', homeTeamName: 'Home FC', awayTeamName: 'Away FC',
  statKey: 'cornerKicks', period: 'ALL', scope: 'total', direction: 'over', lineValue: 10.5,
  selectedOdds: 1.95, predictedWinProbability: 0.61, expectedRoiUnits: 0.1895,
  modelId: 'v6', modelStatus: 'forward_test_only', policyId: 'policy-1', policyStatus: 'shadow',
  snapshotKey: 'snapshot-t3d', snapshotLabel: 'T_MINUS_3D', checkpointLabels: ['T_MINUS_3D'],
  observationCount: 1, settledObservationCount: 1, offerKey: 'offer-1', oddsSnapshotTime: '2026-08-12T12:00:00Z',
  predictionCreatedAt: '2026-08-12T12:01:00Z', matchStartTime: '2026-08-15T12:00:00Z',
  validForForwardEvaluation: true, invalidForModel: false, selectionFamily: 'v6' as const,
  resultStatus: 'settled', settlementStatus: 'settled', settlementResult: 'win' as const, actualValue: 12,
  pnlUnits: 0.95, stakeUnits: 1, validForPerformance: true,
  acceptedClv: true, officialClv: false, acceptedClvCount: 1, t30ClvCount: 1, t10ClvCount: 0,
  closingStatus: 'accepted' as const, closingQuality: 't30_fallback', closingCheckpoint: 'T_MINUS_30M',
  closingOdds: 1.8, clvStatus: 'tracked_fallback_t30', clvPct: 8.3, clvDistancePct: 8.3,
  beatClosingLine: true, beatClosingLineCount: 1, averageClvPct: 8.3,
  oddsHistory: [
    { snapshotLabel: 'T_MINUS_3D', observedAt: '2026-08-12T12:00:00Z', odds: 1.95, lineValue: 10.5, selected: true, closing: false },
    { snapshotLabel: 'T_MINUS_2H', observedAt: '2026-08-15T10:00:00Z', odds: 1.88, lineValue: 10.5, selected: false, closing: false },
    { snapshotLabel: 'T_MINUS_30M', observedAt: '2026-08-15T11:30:00Z', odds: 1.8, lineValue: 10.5, selected: false, closing: true },
  ],
};

const autoResponse = {
  count: 1,
  observationCount: 1,
  rawCount: 1,
  excludedComboLegCount: 0,
  excludedShadowPredictionCount: 0,
  collapsedDuplicateCount: 0,
  summary: {
    total: 1, groups: 1, valid: 1, excluded: 0, acceptedClvCount: 1,
    t30ClvCount: 1, t10ClvCount: 0, beatClosingLineCount: 1, averageAcceptedClvPct: 8.3,
  },
  page: { limit: 50, offset: 0, hasMore: false },
  selections: [selection],
};

function requestUrl(input: RequestInfo | URL): string {
  return typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
}

describe('Spel & resultat med accepterad CLV', () => {
  it('ersätter Auto och Resultatloop med en enda yta och visar T30-CLV', async () => {
    renderApp('/auto', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/auto': autoResponse,
    });

    const main = within(screen.getByRole('main'));
    expect(await main.findByRole('heading', { name: 'Spel & resultat' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Huvudnavigation' });
    expect(within(nav).getByRole('link', { name: 'Spel & resultat' })).toHaveAttribute('href', '/auto');
    expect(within(nav).queryByRole('link', { name: 'Auto' })).not.toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: 'Resultatloop' })).not.toBeInTheDocument();
    expect(main.getByRole('columnheader', { name: 'CLV' })).toBeInTheDocument();
    expect(main.getAllByText('+8,3 %').length).toBeGreaterThanOrEqual(2);
    expect(main.getByText('Slog close med 8,3 % · T-30')).toBeInTheDocument();
    expect(main.getByText('1/1 slog close · 1 T-30 · 0 T-10')).toBeInTheDocument();
  });

  it('öppnar oddsrörelsen med hover-, fokus- och touch-kompatibel kontroll', async () => {
    renderApp('/auto', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/auto': autoResponse,
    });

    const trigger = await screen.findByRole('button', { name: 'Visa oddsrörelse för Home FC mot Away FC' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    fireEvent.pointerEnter(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('heading', { name: 'Oddsrörelse & closing' })).toBeInTheDocument();
    expect(screen.getByText('T-3D')).toBeInTheDocument();
    expect(screen.getByText('T-2H')).toBeInTheDocument();
    expect(screen.getAllByText('T-30').length).toBeGreaterThan(0);
    expect(screen.getByText('Closing 1,80')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    fireEvent.focus(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    fireEvent.focus(screen.getByRole('button', { name: 'Stäng oddsrörelse' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('leder gamla Resultatloop-länkar till rättade spel i samma Auto-kontrakt', async () => {
    const { fetchMock } = renderApp('/resultatloop?date=2026-08-13', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/auto': autoResponse,
    });

    expect(await screen.findByRole('heading', { name: 'Spel & resultat' })).toBeInTheDocument();
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([input]) => requestUrl(input));
      expect(calls.some((url) => url.startsWith('/api/v1/auto?') && new URLSearchParams(url.split('?')[1]).get('status') === 'settled')).toBe(true);
      expect(calls.some((url) => url.startsWith('/api/v1/results'))).toBe(false);
    });
    expect(screen.getByRole('button', { name: 'Rättade' })).toHaveAttribute('aria-pressed', 'true');
  });
});
