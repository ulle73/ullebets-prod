import type { MatchDetail, MatchSummary, Signal } from '../domain/types';

export const previewMatches: MatchSummary[] = [
  {
    matchKey: 'gremio-sao-paulo',
    startTime: '2026-08-08T19:00:00Z',
    leagueName: 'Brasileirão Betano',
    homeTeamName: 'Grêmio',
    awayTeamName: 'São Paulo',
    status: 'finished',
  },
  {
    matchKey: 'remo-atletico-mineiro',
    startTime: '2026-08-08T21:30:00Z',
    leagueName: 'Brasileirão Betano',
    homeTeamName: 'Remo',
    awayTeamName: 'Atlético Mineiro',
    status: 'scheduled',
  },
  {
    matchKey: 'coritiba-chapecoense',
    startTime: '2026-08-09T00:30:00Z',
    leagueName: 'Brasileirão Betano',
    homeTeamName: 'Coritiba',
    awayTeamName: 'Chapecoense',
    status: 'scheduled',
  },
];

// The market identities mirror the user's legacy Ullebets screenshot. Numeric
// probability/EV/odds fields remain null because no repository evidence maps
// those exact values to these Brazil rows. Brazil is outside V6's fitted domain.
export const previewSignals: Signal[] = [
  {
    id: 'gsp-over-fouls-away-2nd',
    matchKey: 'gremio-sao-paulo',
    direction: 'OVER',
    statKey: 'fouls',
    scope: 'away',
    period: '2ND',
    line: 7.1,
    predictedWinProbability: null,
    expectedRoiUnits: null,
    offeredOdds: null,
    sourceProvider: 'Unibet/Kambi',
    snapshotLabel: 'T-2H',
    evidence: 'excluded',
    evidenceReason: 'Utanför V6:s träningsdomän',
  },
  {
    id: 'gsp-under-offsides-home-all',
    matchKey: 'gremio-sao-paulo',
    direction: 'UNDER',
    statKey: 'offsides',
    scope: 'home',
    period: 'ALL',
    line: 1.7,
    predictedWinProbability: null,
    expectedRoiUnits: null,
    offeredOdds: null,
    sourceProvider: 'Unibet/Kambi',
    snapshotLabel: 'T-2H',
    evidence: 'excluded',
    evidenceReason: 'Utanför V6:s träningsdomän',
  },
  {
    id: 'gsp-under-freekicks-away-all',
    matchKey: 'gremio-sao-paulo',
    direction: 'UNDER',
    statKey: 'freeKicks',
    scope: 'away',
    period: 'ALL',
    line: 14.9,
    predictedWinProbability: null,
    expectedRoiUnits: null,
    offeredOdds: null,
    sourceProvider: 'Unibet/Kambi',
    snapshotLabel: 'T-2H',
    evidence: 'excluded',
    evidenceReason: 'Utanför V6:s träningsdomän',
  },
];

export const previewMatchDetails: Record<string, MatchDetail> = {
  'gremio-sao-paulo': {
    match: previewMatches[0]!,
    signals: previewSignals,
    checkpoints: [
      { label: 'T-3D', state: 'captured', capturedAt: '2026-08-05T10:00:18Z' },
      { label: 'T-2D', state: 'captured', capturedAt: '2026-08-06T07:06:52Z' },
      { label: 'T-1D', state: 'captured', capturedAt: '2026-08-07T07:47:04Z' },
      { label: 'T-2H', state: 'captured', capturedAt: '2026-08-08T17:49:58Z' },
      { label: 'T-30', state: 'missing', capturedAt: null },
      { label: 'T-10', state: 'missing', capturedAt: null },
    ],
    teamStats: [],
    dataState: 'excluded',
    freshnessLabel: 'Sparad verifieringssnapshot · 8 aug',
  },
};
