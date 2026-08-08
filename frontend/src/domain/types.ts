export type ReadState = 'ready' | 'loading' | 'empty' | 'failed' | 'excluded';
export type EvidenceState = 'analysis' | 'forward-test' | 'historical' | 'excluded';
export type MatchupCondition = 'OVER' | 'UNDER';

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
  statusType: string | null;
}

export interface MatchupEntry {
  entryKey: string;
  snapshotDate: string | null;
  matchKey: string;
  leagueKey: string | null;
  leagueName: string | null;
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
  marketBias: unknown;
  leagueBaseline: number | null;
}

export interface DashboardResponse {
  selectedDate: string | null;
  matches: MatchSummary[];
  matchups: MatchupEntry[];
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
}

export interface MatchDetailResponse {
  match: MatchSummary;
  matchups: MatchupEntry[];
  leagueAverageMatchups: Record<string, unknown>[];
  checkpoints: CheckpointReadModel[];
  teamStats: TeamStatRow[];
}

export interface AutoSelection {
  selectionKey: string | null;
  matchKey: string | null;
  homeTeamName: string | null;
  awayTeamName: string | null;
  leagueName: string | null;
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
  matchStartTime: string | null;
  validForForwardEvaluation: boolean | null;
  invalidForModel: boolean;
}

export interface AutoResponse {
  count: number;
  selections: AutoSelection[];
}

export interface ResultsResponse {
  summary: { rows: number; settled: number; wins: number; losses: number; excluded: number };
  rows: Record<string, unknown>[];
}

export interface TeamResponse {
  teamKey: string;
  profiles: Record<string, unknown>[];
}

export interface ModelResponse {
  modelIds: string[];
  policyIds: string[];
  scoreCount: number;
  forwardSelectionCount: number;
  settledForwardCount: number;
  officialClvCount: number;
}

export interface SystemResponse {
  jobs: Record<string, unknown>[];
  health: Record<string, unknown>[];
  audits: Record<string, unknown>[];
}
