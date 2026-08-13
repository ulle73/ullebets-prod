import { describe, expect, it } from 'vitest';
import type { MatchDetailResponse } from '../../domain/types';
import {
  buildFirstGoalView,
  buildShotTempoView,
  buildStatComparison,
  buildTenMinuteView,
} from './view-model';

function detailResponse(): MatchDetailResponse {
  return {
    match: {
      matchKey: 'sofascore:123',
      sourceMatchId: 123,
      sourceDate: '2026-08-09',
      startTime: '2026-08-09T18:00:00Z',
      leagueKey: 'test-league',
      leagueName: 'Test League',
      homeTeamKey: 'home',
      awayTeamKey: 'away',
      homeTeamName: 'Cruzeiro',
      awayTeamName: 'Mirassol',
      homeTeamImageUrl: '/images/home.png',
      awayTeamImageUrl: '/images/away.png',
      statusType: 'notstarted',
      state: 'upcoming',
      homeScore: null,
      awayScore: null,
      resultFetchedAt: null,
    },
    matchups: [],
    matchupSource: 'missing',
    leagueAverageMatchups: [],
    checkpoints: [],
    teamStats: [
      {
        statKey: 'totalShotsOnGoal',
        period: 'ALL',
        homeValue: 14.9,
        awayValue: 10.6,
        homeRank: 3,
        awayRank: 16,
        homeLeagueAverage: 11.7,
        awayLeagueAverage: 11.7,
        homeForValue: 14.9,
        homeAgainstValue: 10.8,
        awayForValue: 10.6,
        awayAgainstValue: 11.7,
        homeForRank: 3,
        homeAgainstRank: 15,
        awayForRank: 16,
        awayAgainstRank: 11,
        homeForLeagueAverage: 11.7,
        homeAgainstLeagueAverage: 11.7,
        awayForLeagueAverage: 11.7,
        awayAgainstLeagueAverage: 11.7,
      },
    ],
    result: null,
    actualStats: [],
    marketOffers: [],
    teamProfiles: {
      home: {
        profileDate: 'current',
        generatedAt: '2026-08-09T12:00:00Z',
        sampleSize: 10,
        specials: {
          shotsPerMinute: {
            for: { leading: 0.11, drawing: 0.19, trailing: 0.22 },
            against: { leading: 0.08, drawing: 0.17, trailing: 0.15 },
          },
          shotsPerTenMinutes: {
            for: { '0-10': 1.88, '11-20': 0.64, '21-30': 1.92 },
            against: { '0-10': 1.56, '11-20': 1.56, '21-30': 1.2 },
          },
          firstGoal: {
            scoreFirstPercentage: 0.727,
            concedeFirstPercentage: 0.273,
            averageTimeScoredFirst: 28.2,
            averageTimeConcededFirst: 24.1,
            'rank-scoreFirstPercentage': 9,
            'rank-concedeFirstPercentage': 15,
          },
          leagueAverage: {
            shotsPerMinute: {
              for: { leading: 0.15, drawing: 0.14, trailing: 0.14 },
              against: { leading: 0.15, drawing: 0.14, trailing: 0.14 },
            },
            shotsPerTenMinutes: {
              for: { '0-10': 1.1, '11-20': 1.0, '21-30': 1.2 },
              against: { '0-10': 1.0, '11-20': 1.1, '21-30': 1.1 },
            },
            firstGoal: {},
          },
        },
      },
      away: {
        profileDate: 'current',
        generatedAt: '2026-08-09T12:00:00Z',
        sampleSize: 10,
        specials: {
          shotsPerMinute: {
            for: { leading: 0.08, drawing: 0.17, trailing: 0.15 },
            against: { leading: 0.11, drawing: 0.19, trailing: 0.22 },
          },
          shotsPerTenMinutes: {
            for: { '0-10': 1.04, '11-20': 1.16, '21-30': 1.56 },
            against: { '0-10': 1.36, '11-20': 1.08, '21-30': 1.4 },
          },
          firstGoal: {
            scoreFirstPercentage: 0.241,
            concedeFirstPercentage: 0.282,
            averageTimeScoredFirst: 24.1,
            averageTimeConcededFirst: 28.2,
            'rank-scoreFirstPercentage': 16,
            'rank-concedeFirstPercentage': 1,
          },
          leagueAverage: {
            shotsPerMinute: {
              for: { leading: 0.15, drawing: 0.14, trailing: 0.14 },
              against: { leading: 0.15, drawing: 0.14, trailing: 0.14 },
            },
            shotsPerTenMinutes: {
              for: { '0-10': 1.1, '11-20': 1.0, '21-30': 1.2 },
              against: { '0-10': 1.0, '11-20': 1.1, '21-30': 1.1 },
            },
            firstGoal: {},
          },
        },
      },
    },
  };
}

describe('match detail view models', () => {
  it('builds one shared comparison scale with for and against deltas', () => {
    const row = buildStatComparison(detailResponse(), 'ALL')[0]!;

    expect(row.key).toBe('totalShotsOnGoal');
    expect(row.scaleMax).toBe(14.9);
    expect(row.home.for.ratio).toBe(1);
    expect(row.away.for.ratio).toBeCloseTo(10.6 / 14.9);
    expect(row.forDelta).toEqual({ leader: 'home', value: 4.3 });
    expect(row.againstDelta).toEqual({ leader: 'away', value: 0.9 });
  });

  it('keeps ten-minute intervals ordered and missing windows null', () => {
    const view = buildTenMinuteView(detailResponse());

    expect(view.intervals).toEqual([
      '0-10', '11-20', '21-30', '31-40', '41-50', '51-60', '61-70', '71-80', '81-90',
    ]);
    expect(view.home.forValues.slice(0, 4)).toEqual([1.88, 0.64, 1.92, null]);
    expect(view.away.againstValues.slice(0, 4)).toEqual([1.36, 1.08, 1.4, null]);
    expect(view.scaleMax).toBe(1.92);
  });

  it('positions all first-goal markers on one exact 0-45 axis', () => {
    const view = buildFirstGoalView(detailResponse());

    expect(view.markers).toHaveLength(4);
    expect(view.markers.find((marker) => marker.key === 'home-scored')?.position).toBeCloseTo(28.2 / 45);
    expect(view.markers.find((marker) => marker.key === 'away-conceded')?.position).toBeCloseTo(28.2 / 45);
    expect(view.markers.find((marker) => marker.key === 'home-conceded')?.position).toBeCloseTo(24.1 / 45);
    expect(view.markers.find((marker) => marker.key === 'away-scored')?.position).toBeCloseTo(24.1 / 45);
  });

  it('builds the three score-state shot-tempo comparisons', () => {
    const view = buildShotTempoView(detailResponse());

    expect(view.map((state) => state.key)).toEqual(['leading', 'drawing', 'trailing']);
    expect(view[1]!.home.value).toBe(0.19);
    expect(view[1]!.home.deltaPercent).toBeCloseTo(35.714, 2);
    expect(view[2]!.away.value).toBe(0.15);
  });
});
