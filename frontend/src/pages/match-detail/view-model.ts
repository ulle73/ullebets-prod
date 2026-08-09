import type {
  MatchDetailResponse,
  NullableNumberMap,
  TeamProfileSummary,
  TeamStatRow,
} from '../../domain/types';

export type MatchPeriod = 'ALL' | '1ST' | '2ND';
export type TeamSide = 'home' | 'away';

const STAT_ORDER = [
  'expectedGoals',
  'totalShotsOnGoal',
  'shotsOnGoal',
  'totalShotsInsideBox',
  'touchesInOppBox',
  'passes',
  'accuratePasses',
  'ballPossession',
  'bigChanceCreated',
  'goalkeeperSaves',
  'cornerKicks',
] as const;

export const STAT_LABELS: Record<string, string> = {
  expectedGoals: 'Expected goals (xG)',
  totalShotsOnGoal: 'Total shots',
  shotsOnGoal: 'Shots on target',
  totalShotsInsideBox: 'Shots inside box',
  touchesInOppBox: 'Touches in opp box',
  passes: 'Passes',
  accuratePasses: 'Accurate passes',
  ballPossession: 'Possession %',
  bigChanceCreated: 'Big chances',
  goalkeeperSaves: 'Saves',
  cornerKicks: 'Corners',
};

export const TEN_MINUTE_INTERVALS = [
  '0-10',
  '11-20',
  '21-30',
  '31-40',
  '41-50',
  '51-60',
  '61-70',
  '71-80',
  '81-90',
] as const;

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function ratio(value: number | null, max: number): number | null {
  return value === null || max <= 0 ? null : Math.min(Math.max(value / max, 0), 1);
}

function roundedDifference(home: number | null, away: number | null) {
  if (home === null || away === null) return { leader: 'missing' as const, value: null };
  if (home === away) return { leader: 'equal' as const, value: 0 };
  return {
    leader: home > away ? 'home' as const : 'away' as const,
    value: Math.round(Math.abs(home - away) * 100) / 100,
  };
}

function statTeam(
  row: TeamStatRow,
  side: TeamSide,
  scaleMax: number,
) {
  const prefix = side === 'home' ? 'home' : 'away';
  const forValue = numeric(row[`${prefix}ForValue`]);
  const againstValue = numeric(row[`${prefix}AgainstValue`]);
  const forLeagueAverage = numeric(row[`${prefix}ForLeagueAverage`]);
  const againstLeagueAverage = numeric(row[`${prefix}AgainstLeagueAverage`]);
  return {
    for: {
      value: forValue,
      rank: numeric(row[`${prefix}ForRank`]),
      leagueAverage: forLeagueAverage,
      ratio: ratio(forValue, scaleMax),
      leagueRatio: ratio(forLeagueAverage, scaleMax),
    },
    against: {
      value: againstValue,
      rank: numeric(row[`${prefix}AgainstRank`]),
      leagueAverage: againstLeagueAverage,
      ratio: ratio(againstValue, scaleMax),
      leagueRatio: ratio(againstLeagueAverage, scaleMax),
    },
  };
}

export function buildStatComparison(data: MatchDetailResponse, period: MatchPeriod) {
  const order = new Map<string, number>(STAT_ORDER.map((key, index) => [key, index]));
  return [...data.teamStats]
    .filter((row) => row.period === period && order.has(row.statKey))
    .sort((left, right) => (order.get(left.statKey) ?? 99) - (order.get(right.statKey) ?? 99))
    .map((row) => {
      const scaleValues = [
        row.homeForValue,
        row.homeAgainstValue,
        row.awayForValue,
        row.awayAgainstValue,
        row.homeForLeagueAverage,
        row.homeAgainstLeagueAverage,
        row.awayForLeagueAverage,
        row.awayAgainstLeagueAverage,
      ].map(numeric).filter((value): value is number => value !== null);
      const scaleMax = Math.max(...scaleValues, 0);
      return {
        key: row.statKey,
        label: STAT_LABELS[row.statKey] ?? row.statKey,
        scaleMax,
        home: statTeam(row, 'home', scaleMax),
        away: statTeam(row, 'away', scaleMax),
        forDelta: roundedDifference(numeric(row.homeForValue), numeric(row.awayForValue)),
        againstDelta: roundedDifference(numeric(row.homeAgainstValue), numeric(row.awayAgainstValue)),
      };
    });
}

function profileMap(
  profile: TeamProfileSummary | null,
  group: 'shotsPerMinute' | 'shotsPerTenMinutes',
  side: 'for' | 'against',
): NullableNumberMap {
  return profile?.specials[group]?.[side] ?? {};
}

function leagueMap(
  profile: TeamProfileSummary | null,
  group: 'shotsPerMinute' | 'shotsPerTenMinutes',
  side: 'for' | 'against',
): NullableNumberMap {
  return profile?.specials.leagueAverage?.[group]?.[side] ?? {};
}

function deltaPercent(value: number | null, leagueAverage: number | null): number | null {
  if (value === null || leagueAverage === null || leagueAverage === 0) return null;
  return ((value - leagueAverage) / leagueAverage) * 100;
}

export function buildShotTempoView(data: MatchDetailResponse) {
  const states = [
    { key: 'leading', label: 'Leder' },
    { key: 'drawing', label: 'Lika' },
    { key: 'trailing', label: 'Underläge' },
  ] as const;
  return states.map((state) => {
    const homeValue = numeric(profileMap(data.teamProfiles.home, 'shotsPerMinute', 'for')[state.key]);
    const awayValue = numeric(profileMap(data.teamProfiles.away, 'shotsPerMinute', 'for')[state.key]);
    const homeLeague = numeric(leagueMap(data.teamProfiles.home, 'shotsPerMinute', 'for')[state.key]);
    const awayLeague = numeric(leagueMap(data.teamProfiles.away, 'shotsPerMinute', 'for')[state.key]);
    const scaleMax = Math.max(homeValue ?? 0, awayValue ?? 0, homeLeague ?? 0, awayLeague ?? 0);
    return {
      ...state,
      scaleMax,
      home: {
        value: homeValue,
        leagueAverage: homeLeague,
        ratio: ratio(homeValue, scaleMax),
        leagueRatio: ratio(homeLeague, scaleMax),
        deltaPercent: deltaPercent(homeValue, homeLeague),
      },
      away: {
        value: awayValue,
        leagueAverage: awayLeague,
        ratio: ratio(awayValue, scaleMax),
        leagueRatio: ratio(awayLeague, scaleMax),
        deltaPercent: deltaPercent(awayValue, awayLeague),
      },
    };
  });
}

function intervalValues(map: NullableNumberMap): Array<number | null> {
  return TEN_MINUTE_INTERVALS.map((interval) => numeric(map[interval]));
}

export function buildTenMinuteView(data: MatchDetailResponse) {
  const team = (profile: TeamProfileSummary | null) => ({
    forValues: intervalValues(profileMap(profile, 'shotsPerTenMinutes', 'for')),
    againstValues: intervalValues(profileMap(profile, 'shotsPerTenMinutes', 'against')),
    leagueForValues: intervalValues(leagueMap(profile, 'shotsPerTenMinutes', 'for')),
    leagueAgainstValues: intervalValues(leagueMap(profile, 'shotsPerTenMinutes', 'against')),
  });
  const home = team(data.teamProfiles.home);
  const away = team(data.teamProfiles.away);
  const values = [
    ...home.forValues,
    ...home.againstValues,
    ...home.leagueForValues,
    ...home.leagueAgainstValues,
    ...away.forValues,
    ...away.againstValues,
    ...away.leagueForValues,
    ...away.leagueAgainstValues,
  ].filter((value): value is number => value !== null);
  return {
    intervals: [...TEN_MINUTE_INTERVALS],
    home,
    away,
    scaleMax: Math.max(...values, 0),
  };
}

function firstGoal(profile: TeamProfileSummary | null, key: string): number | null {
  return numeric(profile?.specials.firstGoal?.[key]);
}

export function buildFirstGoalView(data: MatchDetailResponse) {
  const home = data.teamProfiles.home;
  const away = data.teamProfiles.away;
  const marker = (
    key: string,
    side: TeamSide,
    event: 'scored' | 'conceded',
    minute: number | null,
  ) => ({
    key,
    side,
    event,
    minute,
    position: minute === null ? null : Math.min(Math.max(minute / 45, 0), 1),
  });
  return {
    home: {
      scoreFirstPercentage: firstGoal(home, 'scoreFirstPercentage'),
      concedeFirstPercentage: firstGoal(home, 'concedeFirstPercentage'),
      scoreFirstRank: firstGoal(home, 'rank-scoreFirstPercentage'),
      concedeFirstRank: firstGoal(home, 'rank-concedeFirstPercentage'),
    },
    away: {
      scoreFirstPercentage: firstGoal(away, 'scoreFirstPercentage'),
      concedeFirstPercentage: firstGoal(away, 'concedeFirstPercentage'),
      scoreFirstRank: firstGoal(away, 'rank-scoreFirstPercentage'),
      concedeFirstRank: firstGoal(away, 'rank-concedeFirstPercentage'),
    },
    markers: [
      marker('home-scored', 'home', 'scored', firstGoal(home, 'averageTimeScoredFirst')),
      marker('home-conceded', 'home', 'conceded', firstGoal(home, 'averageTimeConcededFirst')),
      marker('away-scored', 'away', 'scored', firstGoal(away, 'averageTimeScoredFirst')),
      marker('away-conceded', 'away', 'conceded', firstGoal(away, 'averageTimeConcededFirst')),
    ],
  };
}

export type StatComparisonRow = ReturnType<typeof buildStatComparison>[number];
export type ShotTempoState = ReturnType<typeof buildShotTempoView>[number];
export type TenMinuteView = ReturnType<typeof buildTenMinuteView>;
export type FirstGoalView = ReturnType<typeof buildFirstGoalView>;
