import type { PeriodKey, ScopeKey, StatKey } from './formatters';

export type MatchStatus = 'scheduled' | 'finished';
export type Direction = 'OVER' | 'UNDER';
export type EvidenceState = 'analysis' | 'forward-test' | 'historical' | 'excluded';
export type ReadState = 'ready' | 'loading' | 'empty' | 'failed' | 'excluded';

export interface MatchSummary {
  matchKey: string;
  startTime: string;
  leagueName: string;
  homeTeamName: string;
  awayTeamName: string;
  status: MatchStatus;
}

export interface Signal {
  id: string;
  matchKey: string;
  direction: Direction;
  statKey: StatKey;
  scope: ScopeKey;
  period: PeriodKey;
  line: number;
  predictedWinProbability: number | null;
  expectedRoiUnits: number | null;
  offeredOdds: number | null;
  sourceProvider: 'Unibet/Kambi';
  snapshotLabel: string;
  evidence: EvidenceState;
  evidenceReason: string;
}

export interface Checkpoint {
  label: string;
  state: 'captured' | 'not-yet' | 'fallback' | 'missing';
  capturedAt: string | null;
}

export interface TeamStatComparison {
  label: string;
  homeValue: number | null;
  awayValue: number | null;
  leagueAverage: number | null;
}

export interface MatchDetail {
  match: MatchSummary;
  signals: Signal[];
  checkpoints: Checkpoint[];
  teamStats: TeamStatComparison[];
  dataState: ReadState;
  freshnessLabel: string;
}
