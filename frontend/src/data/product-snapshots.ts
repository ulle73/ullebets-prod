export const autoEvidenceSnapshot = {
  asOf: '2026-08-08',
  actionableSelections: 0,
  inDomainScores: 0,
  outOfDomainScores: 48,
  status: 'BLOCKED',
  supportedLeagues: [
    'A-League Men',
    'Bundesliga',
    'La Liga',
    'Ligue 1',
    'Premier League',
    'Italian Serie A',
  ],
} as const;

export const operationalResultsSnapshot = {
  asOf: '2026-07-31',
  settled: 64,
  excludedTiming: 3,
  wins: 26,
  losses: 38,
  coritibaCruzeiro: {
    match: 'Coritiba – Cruzeiro',
    result: '0–1',
    forwardRows: 9,
    wins: 4,
    losses: 5,
  },
  diagnosticEvShadow: {
    rows: 5,
    wins: 2,
    losses: 3,
    pnlUnits: -1.17,
    roiPct: -23.4,
    evidence: 'Brasilien OOD-diagnostik',
  },
} as const;

export const teamProfileFixture = {
  source: 'tests/v2/test_teamprofiles.py',
  profileDate: '2025-12-01',
  slug: 'adelaide-united',
  teamName: 'Adelaide United',
  leagueName: 'A-League Men',
  context: 'Home profile',
  cornerAll: {
    value: 5.0,
    rank: 1,
    leagueAverage: null,
  },
  comparisonTeam: {
    teamName: 'Melbourne City',
    value: 6.5,
    rank: 1,
  },
} as const;

export const modelEvidenceSnapshot = {
  asOf: '2026-08-08',
  model: 'V6',
  forwardPolicy: 'v6_corners_away_total_forward_v1',
  historical: {
    bets: 156,
    matches: 99,
    pnlUnits: 44.7,
    roiPct: 28.65,
    intervalLowPct: 11.33,
    intervalHighPct: 45.27,
  },
  forward: {
    status: 'BLOCKED',
    inDomainScores: 0,
    selections: 0,
    settlements: 0,
    roiRows: 0,
    clvRows: 0,
  },
  supportedLeagues: autoEvidenceSnapshot.supportedLeagues,
} as const;

export const systemEvidenceSnapshot = {
  label: 'Sparad verifieringssnapshot · 8 aug 2026',
  checkpointRows: [
    { label: 'T-3D', rows: 678, matches: 10, status: 'VERIFIED' },
    { label: 'T-2D', rows: 799, matches: 10, status: 'VERIFIED' },
    { label: 'T-1D', rows: 817, matches: 10, status: 'VERIFIED' },
    { label: 'T-2H', rows: 242, matches: 3, status: 'VERIFIED' },
    { label: 'T-30', rows: null, matches: null, status: 'UNPROVEN' },
    { label: 'T-10', rows: null, matches: null, status: 'UNPROVEN' },
  ],
  closingLines: 0,
  clvState: 'UNPROVEN',
  v6CaptureScoring: 'PARTIAL',
} as const;
