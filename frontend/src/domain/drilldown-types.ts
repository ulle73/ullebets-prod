import type { AutoSelection, ForwardResult, LeagueResponse, MatchDetailResponse, TeamProfileContext, TeamProfileGame, TeamResponse } from './types';

export interface LeagueStatRow {
  teamKey: string;
  teamName: string;
  context: 'home' | 'away' | string;
  orientation: 'for' | 'against' | string;
  statKey: string;
  period: string;
  value: number;
  rank: number | null;
  leagueAverage: number | null;
}

export interface RichLeagueResponse extends LeagueResponse {
  statRows: LeagueStatRow[];
}

export interface RichTeamProfileGame extends TeamProfileGame {
  homeScore: number | null;
  awayScore: number | null;
}

export interface RichTeamProfileContext extends Omit<TeamProfileContext, 'games'> {
  games: RichTeamProfileGame[];
}

export interface RichTeamResponse extends Omit<TeamResponse, 'contexts'> {
  contexts: {
    home: RichTeamProfileContext | null;
    away: RichTeamProfileContext | null;
  };
}

export interface RichMatchDetailResponse extends MatchDetailResponse {
  forwardSelections: AutoSelection[];
  forwardResults: ForwardResult[];
}
