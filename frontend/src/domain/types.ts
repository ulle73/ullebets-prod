export type ReadState = 'ready' | 'loading' | 'empty' | 'failed' | 'excluded';
export type EvidenceState = 'analysis' | 'forward-test' | 'historical' | 'excluded';
export type MatchupCondition = 'OVER' | 'UNDER';
export type MatchupSource = 'persisted' | 'computed_read_only' | 'missing';
export type MatchState = 'upcoming' | 'live' | 'finished' | 'postponed' | 'cancelled' | 'unknown';
export type MarketBiasDirection = 'over' | 'under' | 'neutral' | 'insufficient';
export type MarketBiasStrength = 'none' | 'lean' | 'strong' | 'very_strong';

export interface MarketBiasProfileSummary {
  teamKey: string;
  teamName: string;
  venueContext: 'home' | 'away';
  direction: MarketBiasDirection;
  strength: MarketBiasStrength;
  sampleSize: number;
  nonPushSampleSize: number;
  overCount: number;
  underCount: number;
  pushCount: number;
  posteriorOverRate: number;
  shrunkMeanResidual: number;
  directionConfidence: number;
  methodVersion: string;
}

export interface MarketBiasSummary {
  scope: 'total' | 'home' | 'away';
  profiles: MarketBiasProfileSummary[];
}

export interface PageInfo {
  limit: number;
  offset: number;
  hasMore: boolean;
}

export interface MatchSummary {
  matchKey: string;
  sourceMatchId: string | number | null;
  sourceDate: string | null;
  startTime: string | null;
  leagueKey: string | null;
  leagueName: string | null;
  homeTeamKey: string | null;
  awayTeamKey: string | null;
  homeTeamName: string | null;
  awayTeamName: string | null;
  homeTeamImageUrl?: string | null;
  awayTeamImageUrl?: string | null;
  statusType: string | null;
  state: MatchState;
  homeScore: number | null;
  awayScore: number | null;
  resultFetchedAt: string | null;
}

export interface MatchupEntry {
  entryKey: string;
  snapshotDate: string | null;
  matchKey: string;
  leagueKey: string | null;
  leagueName: string | null;
  homeTeamKey: string | null;
  awayTeamKey: string | null;
  homeTeamName: string | null;
  awayTeamName: string | null;
  statKey: string | null;
  statLabel: string | null;
  period: string | null;
  periodLabel: string | null;
  scope: string | null;
  condition: MatchupCondition;
  score: number | null;
  rankPosition: number | null;
  isTop50: boolean;
  rankingMethod: string | null;
  rankingWindowMatches: number | null;
  rankingRecencyHalfLifeDays: number | null;
  marketBias: MarketBiasSummary | null;
  leagueBaseline: number | null;
}

export interface DashboardResponse {
  selectedDate: string;
  timezone: string;
  generatedAt: string;
  matches: MatchSummary[];
  matchups: MatchupEntry[];
  matchupSource: MatchupSource;
}

export interface MatchesResponse {
  matches: MatchSummary[];
}

export interface CheckpointReadModel {
  label: string;
  snapshotType: string | null;
  capturedAt: string | null;
  minutesToKickoff: number | null;
  invalidForModel: boolean;
}

export interface TeamStatRow {
  statKey: string;
  period: string;
  homeValue: number | null;
  awayValue: number | null;
  homeRank: number | null;
  awayRank: number | null;
  homeLeagueAverage: number | null;
  awayLeagueAverage: number | null;
  homeForValue: number | null;
  homeAgainstValue: number | null;
  awayForValue: number | null;
  awayAgainstValue: number | null;
  homeForRank: number | null;
  homeAgainstRank: number | null;
  awayForRank: number | null;
  awayAgainstRank: number | null;
  homeForLeagueAverage: number | null;
  homeAgainstLeagueAverage: number | null;
  awayForLeagueAverage: number | null;
  awayAgainstLeagueAverage: number | null;
}

export type NullableNumberMap = Record<string, number | null>;

export interface TeamProfileSpecialPair {
  for: NullableNumberMap;
  against: NullableNumberMap;
}

export interface TeamProfileSpecials {
  shotsPerMinute: TeamProfileSpecialPair;
  shotsPerTenMinutes: TeamProfileSpecialPair;
  firstGoal: NullableNumberMap;
  leagueAverage: {
    shotsPerMinute: TeamProfileSpecialPair;
    shotsPerTenMinutes: TeamProfileSpecialPair;
    firstGoal: NullableNumberMap;
  };
}

export interface TeamProfileSummary {
  profileDate: string | null;
  generatedAt: string | null;
  sampleSize: number;
  specials: TeamProfileSpecials;
}

export interface MatchResultSummary {
  homeScore: number | null;
  awayScore: number | null;
  fetchedAt: string | null;
  mappingConfidence: string | null;
  hasMatchDetails: boolean | null;
  hasIncidents: boolean | null;
  hasShotmap: boolean | null;
}

export interface ActualStatRow {
  statKey: string | null;
  period: string | null;
  scope: string | null;
  actualValue: number | null;
  mappingConfidence: string | null;
}

export interface MarketOffer {
  offerKey: string | null;
  eventId: string | null;
  statKey: string | null;
  scope: string | null;
  period: string | null;
  line: number | null;
  overOdds: number | null;
  underOdds: number | null;
  sourceProvider: string | null;
  payloadKind: string | null;
  updatedAt: string | null;
  modelSupport?: 'supported' | 'partially_supported' | 'model_missing';
  modelSupportReason?: string | null;
  supportedDirections?: string[];
}

export interface MatchDetailResponse {
  match: MatchSummary;
  matchups: MatchupEntry[];
  matchupSource: MatchupSource;
  leagueAverageMatchups: Record<string, unknown>[];
  checkpoints: CheckpointReadModel[];
  teamStats: TeamStatRow[];
  result: MatchResultSummary | null;
  actualStats: ActualStatRow[];
  marketOffers: MarketOffer[];
  teamProfiles: {
    home: TeamProfileSummary | null;
    away: TeamProfileSummary | null;
  };
  forwardSelections?: AutoSelection[];
  forwardResults?: ForwardResult[];
}

export interface LeagueSummary {
  leagueKey: string;
  leagueName: string | null;
  leagueId: string | number | null;
  country: string | null;
  seasonId: string | number | null;
  categoryId: string | number | null;
  groupId: string | number | null;
  capturedAt: string | null;
}

export interface TeamSummary {
  teamKey: string;
  leagueKey: string | null;
  teamId: string | number | null;
  teamName: string | null;
  teamImageUrl: string | null;
  optaId: string | number | null;
  optaRank: number | null;
  optaRating: number | null;
  capturedAt: string | null;
}

export interface LeagueRanking {
  rankingType: string | null;
  leagueAverageOptaRating: number | null;
  data: unknown;
  capturedAt: string | null;
}

export interface LeagueResponse {
  league: LeagueSummary;
  teams: TeamSummary[];
  ranking: LeagueRanking | null;
  matches: MatchSummary[];
}

export interface TeamProfileHistoryRow {
  matchId?: string | number | null;
  date?: string | null;
  timestamp?: number | null;
  opp?: string | null;
  val?: number | null;
  oppVal?: number | null;
}

export interface TeamProfileStatNode {
  value?: number | null;
  rank?: number | null;
  history?: TeamProfileHistoryRow[];
}

export type TeamProfilePeriods = Record<string, TeamProfileStatNode>;
export type TeamProfileStats = Record<string, TeamProfilePeriods>;

export interface TeamProfileStatistics {
  for?: TeamProfileStats;
  against?: TeamProfileStats;
  leagueAverage?: {
    for?: TeamProfileStats;
    against?: TeamProfileStats;
  };
}

export interface TeamProfileGame {
  matchId: string | number | null;
  matchKey: string | null;
  date: string | null;
  timestamp: number | null;
  opponentName: string | null;
  opponentTeamKey: string | null;
}

export interface TeamProfileContext {
  profileKey: string | null;
  profileDate: string | null;
  generatedAt: string | null;
  matchType: string | null;
  leagueTeamCount: number | null;
  savedAt: string | null;
  games: TeamProfileGame[];
  statistics: TeamProfileStatistics;
  specials: unknown;
  behaviour: unknown;
}

export interface TeamResponse {
  team: TeamSummary;
  league: LeagueSummary | null;
  contexts: {
    home: TeamProfileContext | null;
    away: TeamProfileContext | null;
  };
  matches: MatchSummary[];
}

export interface AutoSelection {
  selectionKey: string | null;
  predictionKey: string | null;
  matchKey: string | null;
  leagueKey: string | null;
  leagueName: string | null;
  homeTeamKey: string | null;
  awayTeamKey: string | null;
  homeTeamName: string | null;
  awayTeamName: string | null;
  statKey: string | null;
  period: string | null;
  scope: string | null;
  direction: string | null;
  lineValue: number | null;
  selectedOdds: number | null;
  predictedWinProbability: number | null;
  expectedRoiUnits: number | null;
  modelId: string | null;
  modelStatus: string | null;
  policyId: string | null;
  policyStatus: string | null;
  snapshotKey: string | null;
  snapshotLabel?: string | null;
  selectionGranularity?: string | null;
  canonicalExposureKey?: string | null;
  observationCount?: number;
  checkpointLabels?: string[];
  bestSnapshotLabel?: string | null;
  bestExpectedRoiUnits?: number | null;
  settledObservationCount?: number;
  officialClvCount?: number;
  acceptedClvCount?: number;
  t30ClvCount?: number;
  t10ClvCount?: number;
  beatClosingLineCount?: number;
  clvBeatRate?: number | null;
  averageClvPct?: number | null;
  acceptedClv?: boolean;
  officialClv?: boolean;
  closingStatus?: 'accepted' | 'not_accepted' | 'missing';
  closingQuality?: string | null;
  closingCheckpoint?: string | null;
  closingOdds?: number | null;
  clvStatus?: string | null;
  clvPct?: number | null;
  clvDistancePct?: number | null;
  beatClosingLine?: boolean | null;
  oddsHistory?: OddsHistoryPoint[];
  offerKey: string | null;
  oddsSnapshotTime: string | null;
  predictionCreatedAt: string | null;
  matchStartTime: string | null;
  validForForwardEvaluation: boolean | null;
  invalidForModel: boolean;
  selectionFamily: 'v6' | 'legacy' | null;
  resultStatus: string | null;
  settlementStatus: string | null;
  settlementResult: 'win' | 'loss' | 'push' | null;
  actualValue: number | null;
  pnlUnits: number | null;
  stakeUnits: number | null;
  roiUnits?: number | null;
  groupStakeUnits?: number | null;
  groupPnlUnits?: number | null;
  groupRoiUnits?: number | null;
  validForPerformance: boolean | null;
}

export interface AutoResponse {
  count: number;
  observationCount?: number;
  rawCount: number;
  excludedComboLegCount: number;
  excludedShadowPredictionCount: number;
  collapsedDuplicateCount: number;
  summary: {
    total: number;
    groups?: number;
    valid: number;
    excluded: number;
    acceptedClvCount?: number;
    t30ClvCount?: number;
    t10ClvCount?: number;
    beatClosingLineCount?: number;
    averageAcceptedClvPct?: number | null;
  };
  page: PageInfo;
  selections: AutoSelection[];
}

export interface OddsHistoryPoint {
  snapshotLabel: string | null;
  observedAt: string | null;
  odds: number;
  lineValue: number | null;
  selected: boolean;
  closing: boolean;
}

export interface ForwardResult {
  resultLoopKey: string | null;
  predictionKey: string | null;
  selectionKey: string | null;
  trackingKey: string | null;
  matchKey: string | null;
  leagueKey: string | null;
  leagueName: string | null;
  homeTeamKey: string | null;
  awayTeamKey: string | null;
  homeTeamName: string | null;
  awayTeamName: string | null;
  statKey: string | null;
  period: string | null;
  scope: string | null;
  direction: string | null;
  lineValue: number | null;
  snapshotKey?: string | null;
  snapshotLabel?: string | null;
  selectionGranularity?: string | null;
  canonicalExposureKey?: string | null;
  observationCount?: number;
  checkpointLabels?: string[];
  bestSnapshotLabel?: string | null;
  bestExpectedRoiUnits?: number | null;
  settledObservationCount?: number;
  savedOdds: number | null;
  savedAt: string | null;
  oddsSnapshotTime: string | null;
  predictionCreatedAt: string | null;
  matchStartTime: string | null;
  settlementStatus: string | null;
  settlementResult: string | null;
  actualValue: number | null;
  homeValue: number | null;
  awayValue: number | null;
  win: boolean | null;
  roiUnits: number | null;
  pnlUnits: number | null;
  stakeUnits: number | null;
  groupStakeUnits?: number | null;
  groupPnlUnits?: number | null;
  groupRoiUnits?: number | null;
  actualSource: string | null;
  actualSourceStatus: string | null;
  settledAt: string | null;
  validForPerformance: boolean | null;
  invalidForModel: boolean;
  resultLoopStatus: string | null;
  statusReason: string | null;
  openingOdds: number | null;
  latestObservedOdds: number | null;
  closingOdds: number | null;
  closingQuality: string | null;
  closingSnapshotLabel: string | null;
  closingSnapshotTime: string | null;
  acceptedClv?: boolean;
  officialClv: boolean;
  clvBasis: string | null;
  clvStatus: string | null;
  clvPct: number | null;
  clvDistancePct?: number | null;
  beatClosingLine: boolean | null;
  closingStatus?: 'accepted' | 'not_accepted' | 'missing';
  closingCheckpoint?: string | null;
  acceptedClvCount?: number;
  t30ClvCount?: number;
  t10ClvCount?: number;
  officialClvCount?: number;
  beatClosingLineCount?: number;
  clvBeatRate?: number | null;
  averageClvPct?: number | null;
  prematchObservationCount: number | null;
  oddsHistory?: OddsHistoryPoint[];
  refreshedAt: string | null;
}

export interface ResultsResponse {
  summary: {
    rows: number;
    groups?: number;
    settled: number;
    wins: number;
    losses: number;
    pushes: number;
    excluded: number;
    stakeUnits?: number;
    pnlUnits?: number;
    roiPct?: number | null;
    officialClvObservations?: number;
    beatClosingLine?: number;
    clvBeatRatePct?: number | null;
  };
  page: PageInfo;
  rows: ForwardResult[];
}

export interface ModelResponse {
  modelIds: string[];
  policyIds: string[];
  modelStatuses: string[];
  policyStatuses: string[];
  scoreCount: number;
  forwardSelectionCount: number;
  settledForwardCount: number;
  officialClvCount: number;
}

export type FormulaEvidenceLevel = 'early' | 'growing' | 'comparable';

export interface FormulaPerformanceMetrics {
  formulaId: string | null;
  formulaLabel: string | null;
  formulaFamily: string | null;
  observations: number;
  shadowBets: number;
  settled: number;
  settledBets: number;
  uniqueMatches: number;
  uniqueSettledMatches: number;
  wins: number;
  losses: number;
  pushes: number;
  stakeUnits: number;
  pnlUnits: number;
  roiPct: number | null;
  averagePredictedProbabilityPct: number | null;
  averageEvPct: number | null;
  calibrationObservations: number;
  brierScore: number | null;
  logLoss: number | null;
  officialClvObservations: number;
  averageClvPct: number | null;
  beatClosingLine: number;
  clvBeatRatePct: number | null;
  evidenceLevel: FormulaEvidenceLevel;
}

export interface FormulaPerformanceFacet {
  value: string;
  label: string;
  count: number;
}

export interface FormulaPerformanceResponse {
  generatedAt: string;
  mode: 'positive_ev' | 'all_scores';
  summary: FormulaPerformanceMetrics;
  facets: {
    formulas: FormulaPerformanceFacet[];
    families: FormulaPerformanceFacet[];
    stats: FormulaPerformanceFacet[];
    scopes: FormulaPerformanceFacet[];
    periods: FormulaPerformanceFacet[];
    directions: FormulaPerformanceFacet[];
    leagues: FormulaPerformanceFacet[];
    checkpoints: FormulaPerformanceFacet[];
  };
  page: PageInfo;
  groups: FormulaPerformanceMetrics[];
}

export interface SystemResponse {
  jobs: Record<string, unknown>[];
  health: Record<string, unknown>[];
  audits: Record<string, unknown>[];
}
