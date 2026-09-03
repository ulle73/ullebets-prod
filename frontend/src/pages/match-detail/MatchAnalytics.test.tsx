import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { MatchDetailResponse, TeamStatRow } from '../../domain/types';
import { renderApp } from '../../test/render-app';

function stat(period: 'ALL' | '1ST', homeForValue: number): TeamStatRow {
  return {
    statKey: 'totalShotsOnGoal',
    period,
    homeValue: homeForValue,
    awayValue: 10.6,
    homeRank: 3,
    awayRank: 16,
    homeLeagueAverage: 11.7,
    awayLeagueAverage: 11.7,
    homeForValue,
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
  };
}

const detail: MatchDetailResponse = {
  match: {
    matchKey: 'sofascore:123',
    sourceMatchId: 123,
    sourceDate: '2026-08-09',
    startTime: '2026-08-09T18:00:00Z',
    leagueKey: 'test-league',
    leagueName: 'Brasileirão Betano',
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
  teamStats: [stat('ALL', 14.9), stat('1ST', 7.1)],
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
          for: {
            '0-10': 1.88, '11-20': 0.64, '21-30': 1.92, '31-40': 0.6, '41-50': 1.56,
            '51-60': 1, '61-70': 1.68, '71-80': 0.64, '81-90': 1.8,
          },
          against: {
            '0-10': 1.56, '11-20': 1.56, '21-30': 1.2, '31-40': 0.96, '41-50': 1.2,
            '51-60': 0.84, '61-70': 1.08, '71-80': 1.04, '81-90': 1.16,
          },
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
            for: { '0-10': 1.1, '11-20': 1, '21-30': 1.2 },
            against: { '0-10': 1, '11-20': 1.1, '21-30': 1.1 },
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
          for: {
            '0-10': 1.04, '11-20': 1.16, '21-30': 1.56, '31-40': 0.56, '41-50': 1.56,
            '51-60': 0.96, '61-70': 1.2, '71-80': 0.84, '81-90': 1.36,
          },
          against: {
            '0-10': 1.36, '11-20': 1.08, '21-30': 1.4, '31-40': 0.88, '41-50': 1.08,
            '51-60': 1.2, '61-70': 1, '71-80': 1.04, '81-90': 1.32,
          },
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
            for: { '0-10': 1.1, '11-20': 1, '21-30': 1.2 },
            against: { '0-10': 1, '11-20': 1.1, '21-30': 1.1 },
          },
          firstGoal: {},
        },
      },
    },
  },
};

describe('match analytics page', () => {
  it('renders the selected statistics design from one match request', async () => {
    const user = userEvent.setup();
    const { fetchMock } = renderApp('/matcher/sofascore%3A123', {
      '/api/v1/matches/match-123': detail,
    });

    expect(await screen.findByRole('heading', { name: 'Cruzeiro mot Mirassol' }, { timeout: 15_000 })).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/matches/match-123');
    expect(screen.getByRole('img', { name: 'Cruzeiro klubbmärke' }).querySelector('img')).toHaveAttribute('src', '/images/teams/home.png');
    expect(screen.getByRole('img', { name: 'Mirassol klubbmärke' }).querySelector('img')).toHaveAttribute('src', '/images/teams/away.png');

    const comparison = screen.getByRole('table', { name: 'Lagstatistik för och emot' });
    expect(within(comparison).getByText('För')).toBeInTheDocument();
    expect(within(comparison).getByText('Emot')).toBeInTheDocument();
    expect(within(comparison).getByText('CRU +4,3')).toBeInTheDocument();
    expect(within(comparison).getByText('MIR +0,9')).toBeInTheDocument();

    expect(screen.getAllByRole('figure', { name: /Skottempo/i })).toHaveLength(3);
    expect(screen.getByRole('figure', { name: 'Cruzeiro skott per 10 minuter' })).toBeInTheDocument();
    expect(screen.getByRole('figure', { name: 'Mirassol skott per 10 minuter' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Första mål på tidsaxel 0 till 45 minuter/i })).toBeInTheDocument();
    expect(screen.getByText("28,2'")).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Första halvlek' }));
    expect(within(comparison).getByText('7,1')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('tab', { name: 'Lag & odds' }));
    expect(screen.getByText('Inga checkpoints för matchen')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Backtest' }));
    expect(screen.getByText('Ingen matchup-ranking')).toBeInTheDocument();
  }, 15_000);
});
