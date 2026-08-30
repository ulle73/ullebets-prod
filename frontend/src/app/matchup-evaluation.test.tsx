import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const evaluation = {
  predictor: { status: 'resolved', actualValue: 14, leagueBaseline: 11.7, signedResidual: 2.3, verdict: 'hit' as const },
  market: { eligibility: 'eligible', line: 10.5, selectedOdds: 2.18, verdict: 'win' as const, stakeUnits: 1, pnlUnits: 1.18 },
  closing: {
    quality: 't30_fallback', checkpoint: 'T_MINUS_30M', closingOdds: 2.12, clvPct: 2.83, beatClosing: true,
    oddsHistory: [
      { snapshotLabel: 'T_MINUS_1D', observedAt: '2026-08-21T12:00:00Z', odds: 2.18, lineValue: 10.5, selected: true, closing: false },
      { snapshotLabel: 'T_MINUS_30M', observedAt: '2026-08-22T17:30:00Z', odds: 2.12, lineValue: 10.5, selected: false, closing: true },
    ],
  },
  provenance: { evidenceClass: 'legacy_descriptive' as const, validForPredictor: false, rankingMethod: 'rolling_12_weighted_45d' },
};

const dashboard = {
  selectedDate: '2026-08-22', timezone: 'Europe/Stockholm', generatedAt: '2026-08-22T20:00:00Z', matchupSource: 'persisted',
  matches: [{ matchKey: 'm1', sourceMatchId: 1, sourceDate: '2026-08-22', startTime: '2026-08-22T18:00:00Z', leagueKey: 'test', leagueName: 'Test League', homeTeamKey: 'home', awayTeamKey: 'away', homeTeamName: 'Home FC', awayTeamName: 'Away FC', statusType: 'finished', state: 'finished', homeScore: 1, awayScore: 0, resultFetchedAt: null }],
  matchups: [{ entryKey: 'row-1', snapshotDate: '2026-08-22', matchKey: 'm1', leagueKey: 'test', leagueName: 'Test League', homeTeamKey: 'home', awayTeamKey: 'away', homeTeamName: 'Home FC', awayTeamName: 'Away FC', statKey: 'cornerKicks', statLabel: 'Hörnor', period: 'ALL', periodLabel: 'Hela matchen', scope: 'total', condition: 'OVER', score: 82, rankPosition: 1, isTop50: true, rankingMethod: 'rolling_12_weighted_45d', rankingWindowMatches: 12, rankingRecencyHalfLifeDays: 45, marketBias: null, leagueBaseline: 11.7, evaluation }],
};

const summary = {
  filters: { dateFrom: '2026-08-22', dateTo: '2026-08-22' },
  predictor: {
    contexts: 1, resolved: 1, pending: 0, missingActual: 0, hits: 1, misses: 0, pushes: 0, nonPushHitRatePct: 100,
    medianSignedResidual: 2.3,
    constantDirectionBaseline: { overHitRatePct: 50, underHitRatePct: 50, bestDirection: 'tie' as const, bestHitRatePct: 50, liftPctPoints: 50 },
    scoreBuckets: [
      { key: '80_89' as const, label: '80–89,9', resolved: 1, nonPush: 1, hits: 1, misses: 0, pushes: 0, nonPushHitRatePct: 100, medianSignedResidual: 2.3 },
    ],
  },
  market: { eligible: 1, resolved: 1, stakeUnits: 1, pnlUnits: 1.18, roiPct: 118, closingCovered: 1, meanClvPct: 2.83, beatClosing: 1 },
  coverage: { marketEligiblePct: 100 }, legacyDescriptive: { resolved: 1, nonPushHitRatePct: 100 }, evidence: { predictorState: 'thin', marketState: 'thin', criteria: {} },
};

describe('Rättade matchups', () => {
  it('visar prediktor, marknadsutfall, odds movement och CLV', async () => {
    renderApp('/oversikt?date=2026-08-22', {
      '/api/v1/dashboard': dashboard,
      '/api/v1/matchups/evaluation': summary,
    });

    const predictorSummary = await screen.findByRole('region', { name: 'Prediktorresultat' });
    expect(within(predictorSummary).getByText('Prediktor')).toBeInTheDocument();
    expect(within(predictorSummary).getByText('+50,0 pp')).toBeInTheDocument();
    expect(within(predictorSummary).getByText('Mot bästa konstanta riktning')).toBeInTheDocument();
    const marketSummary = screen.getByRole('region', { name: 'Resultat för spelbara marknader' });
    expect(within(marketSummary).getByText('Spelbara marknader')).toBeInTheDocument();
    expect(within(marketSummary).getByText('Closing 1 av 1')).toBeInTheDocument();
    expect(within(marketSummary).getByText('Slog closing 1 av 1')).toBeInTheDocument();
    const diagnosticsLabel = screen.getByText('Rankingpoängens träffsäkerhet');
    fireEvent.click(diagnosticsLabel);
    const diagnostics = diagnosticsLabel.closest('details');
    expect(within(diagnostics!).getByText('80–89,9')).toBeInTheDocument();
    expect(within(diagnostics!).getByText('1 rättad')).toBeInTheDocument();

    expect(await screen.findByRole('img', { name: 'Prediktor: träff' })).toBeInTheDocument();
    expect(screen.queryByText(/TRÄFF|MISS|VUNNEN|FÖRLORAD/)).not.toBeInTheDocument();
    expect(screen.getByText('Rankingpoäng')).toBeInTheDocument();
    expect(screen.getByText('#1 av 1')).toBeInTheDocument();
    const detailLabel = screen.getByText('Prediktor & marknad');
    const details = detailLabel.closest('details');
    expect(details).not.toHaveAttribute('open');
    fireEvent.click(detailLabel);
    expect(details).toHaveAttribute('open');
    expect(screen.getByRole('img', { name: 'Marknad: vunnen' })).toBeInTheDocument();
    expect(within(details!).getByText('Predictortröskel')).toBeInTheDocument();
    expect(within(details!).getByText('Faktiskt utfall')).toBeInTheDocument();
    expect(within(details!).getByText('Avstånd')).toBeInTheDocument();
    expect(within(details!).getByText('+2,3')).toBeInTheDocument();
    expect(within(predictorSummary).getByText('100 %')).toBeInTheDocument();
    const trigger = screen.getByRole('button', { name: /Visa oddsrörelse/ });
    fireEvent.pointerEnter(trigger);
    expect(screen.getByRole('dialog', { name: 'Oddsrörelse & closing' })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    fireEvent.click(trigger);
    expect(screen.getByText(/CLV \+2,8 %/)).toBeInTheDocument();
  }, 15_000);

  it('visar miss och förlust som röda kryss utan synliga statusord', async () => {
    const missDashboard = {
      ...dashboard,
      matchups: dashboard.matchups.map((row) => ({
        ...row,
        evaluation: {
          ...row.evaluation,
          predictor: { ...row.evaluation.predictor, signedResidual: -2.3, verdict: 'miss' as const },
          market: { ...row.evaluation.market, pnlUnits: -1, verdict: 'loss' as const },
        },
      })),
    };
    renderApp('/oversikt?date=2026-08-22', {
      '/api/v1/dashboard': missDashboard,
      '/api/v1/matchups/evaluation': summary,
    });

    expect(await screen.findByRole('img', { name: 'Prediktor: miss' })).toHaveClass('verdict-icon--failure');
    fireEvent.click(screen.getByText('Prediktor & marknad'));
    expect(screen.getByRole('img', { name: 'Marknad: förlorad' })).toHaveClass('verdict-icon--failure');
    expect(screen.queryByText(/TRÄFF|MISS|VUNNEN|FÖRLORAD/)).not.toBeInTheDocument();
  }, 15_000);
});
