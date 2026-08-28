from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import ullebets_v2.read_api.http as read_http
import ullebets_v2.read_api.service as read_service


class MemoryCursor(list):
    def sort(self, spec):
        rows = list(self)
        for field, direction in reversed(spec):
            rows.sort(key=lambda row: _sortable(_get(row, field)), reverse=direction < 0)
        return MemoryCursor(rows)

    def skip(self, value: int):
        return MemoryCursor(self[value:])

    def limit(self, value: int):
        return MemoryCursor(self[:value])


def _sortable(value):
    return (value is None, value)


def _get(row: dict, dotted_key: str):
    value = row
    for part in dotted_key.split('.'):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _matches_value(actual, expected) -> bool:
    if not isinstance(expected, dict):
        return actual == expected
    for operator, value in expected.items():
        if operator == '$in' and actual not in value:
            return False
        if operator == '$ne' and actual == value:
            return False
        if operator == '$gte' and (actual is None or actual < value):
            return False
        if operator == '$lte' and (actual is None or actual > value):
            return False
    return True


def _matches(row: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == '$and':
            if not all(_matches(row, clause) for clause in expected):
                return False
            continue
        if key == '$or':
            if not any(_matches(row, clause) for clause in expected):
                return False
            continue
        if not _matches_value(_get(row, key), expected):
            return False
    return True


class MemoryCollection:
    def __init__(self, rows=()):
        self.rows = [dict(row) for row in rows]

    def find(self, query=None, projection=None):
        del projection
        query = query or {}
        return MemoryCursor([dict(row) for row in self.rows if _matches(row, query)])

    def find_one(self, query=None, projection=None, sort=None):
        cursor = self.find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        return cursor[0] if cursor else None

    def count_documents(self, query=None):
        return len(self.find(query or {}))

    def distinct(self, field, query=None):
        return list(dict.fromkeys(_get(row, field) for row in self.find(query or {}) if _get(row, field) is not None))


class MemoryDatabase(dict):
    def __getitem__(self, key):
        return self.get(key, MemoryCollection())


def fixture(
    match_key: str,
    *,
    source_date: str = '2026-08-13',
    league_key: str = 'league-a',
    league_name: str = 'League A',
    home_key: str = 'team-home',
    away_key: str = 'team-away',
    home_name: str = 'Home FC',
    away_name: str = 'Away FC',
    start_time: datetime | None = None,
):
    kickoff = start_time or datetime.fromisoformat(f'{source_date}T18:00:00+00:00')
    return {
        'match_key': match_key,
        'source_match_id': match_key,
        'source_date': source_date,
        'fixture_date_stockholm': kickoff.astimezone(ZoneInfo('Europe/Stockholm')).date().isoformat(),
        'start_time': kickoff,
        'league_key': league_key,
        'league_name': league_name,
        'home_team_key': home_key,
        'away_team_key': away_key,
        'home_team_name': home_name,
        'away_team_name': away_name,
        'status_type': 'notstarted',
    }


def team_profile(team_key: str, match_type: str, value: float):
    return {
        'profile_key': f'current|{team_key}|{match_type}',
        'team_key': team_key,
        'league_key': 'league-a',
        'match_type': match_type,
        'profile_date': 'current',
        'generated_at': datetime(2026, 8, 12, 20, tzinfo=UTC),
        'games': [
            {
                'matchId': 77,
                'match_key': 'past-77',
                'date': '2026-08-10',
                'timestamp': 1786300000,
                'opp': 'Opponent FC',
                'opponent_team_key': 'opponent',
            }
        ],
        'statistics': {
            'for': {
                'fouls': {
                    'ALL': {
                        'value': value,
                        'rank': 2,
                        'history': [
                            {
                                'matchId': 77,
                                'date': '2026-08-10',
                                'timestamp': 1786300000,
                                'opp': 'Opponent FC',
                                'val': value + 1,
                                'oppVal': value - 2,
                            }
                        ],
                    }
                }
            },
            'against': {'fouls': {'ALL': {'value': value - 1, 'rank': 4}}},
            'leagueAverage': {
                'for': {'fouls': {'ALL': {'value': 10.5}}},
                'against': {'fouls': {'ALL': {'value': 10.2}}},
            },
        },
        'specials': {
            'firstGoal': {'scoreFirstPercentage': 0.6},
            'leagueAverage': {'firstGoal': {'scoreFirstPercentage': 0.5}},
        },
        'meta': {
            'lagnamn': 'Home FC' if team_key == 'team-home' else 'Away FC',
            'leagueName': 'League A',
            'leagueKey': 'league-a',
            'matchType': match_type,
            'leagueTeamCount': 18,
            'savedAt': '2026-08-10',
        },
    }


def test_dashboard_defaults_to_stockholm_product_day_not_latest_database_date() -> None:
    database = MemoryDatabase(
        fixtures_canonical=MemoryCollection(
            [
                fixture('today', source_date='2026-08-13'),
                fixture('future', source_date='2099-01-01'),
            ]
        ),
        matchups_score=MemoryCollection(),
        teamprofiles=MemoryCollection(),
    )

    payload = read_service.read_dashboard(
        database,
        now=datetime(2026, 8, 12, 22, 30, tzinfo=UTC),
    )

    assert payload['selectedDate'] == '2026-08-13'
    assert payload['timezone'] == 'Europe/Stockholm'
    assert payload['generatedAt'].endswith('Z')
    assert [row['matchKey'] for row in payload['matches']] == ['today']


def test_market_bias_contract_is_typed_ordered_and_excludes_internal_provenance() -> None:
    row = {
        'entry_key': 'bias-row',
        'market_bias': {
            'scope': 'total',
            'profiles': [
                {
                    'team_key': 'away', 'team_name': 'Away FC', 'venue_context': 'away',
                    'direction': 'insufficient', 'strength': 'none', 'sample_size': 3,
                    'non_push_sample_size': 2, 'over_count': 1, 'under_count': 1,
                    'push_count': 1, 'posterior_over_rate': 0.5,
                    'shrunk_mean_residual': 0.0, 'direction_confidence': 0.0,
                    'method_version': 'main_line_residual_v1', 'source_payload_hash': 'secret',
                    'observation_keys': ['internal'],
                },
                {
                    'team_key': 'home', 'team_name': 'Home FC', 'venue_context': 'home',
                    'direction': 'over', 'strength': 'strong', 'sample_size': 10,
                    'non_push_sample_size': 10, 'over_count': 7, 'under_count': 3,
                    'push_count': 0, 'posterior_over_rate': 0.625,
                    'shrunk_mean_residual': 1.4, 'direction_confidence': 0.93,
                    'method_version': 'main_line_residual_v1', 'source_payload_hash': 'secret',
                    'observation_keys': ['internal'],
                },
            ],
        },
    }

    summary = read_service._matchup_summary(row)

    assert [profile['teamKey'] for profile in summary['marketBias']['profiles']] == ['home', 'away']
    assert summary['marketBias']['profiles'][1]['direction'] == 'insufficient'
    assert 'sourcePayloadHash' not in summary['marketBias']['profiles'][0]
    assert 'observationKeys' not in summary['marketBias']['profiles'][0]
    assert read_service._matchup_summary({'entry_key': 'none', 'market_bias': {'scope': 'home', 'profiles': []}})['marketBias'] is None


def test_match_resolver_preserves_requested_order_and_enriches_finished_scores() -> None:
    database = MemoryDatabase(
        fixtures_canonical=MemoryCollection([fixture('m1'), fixture('m2')]),
        match_results_canonical=MemoryCollection(
            [
                {
                    'match_key': 'm2',
                    'home_score': 2,
                    'away_score': 1,
                    'fetched_at': datetime(2026, 8, 13, 21, tzinfo=UTC),
                }
            ]
        ),
    )

    payload = read_service.read_matches(database, match_keys=['m2', 'm1'])

    assert [row['matchKey'] for row in payload['matches']] == ['m2', 'm1']
    assert payload['matches'][0]['homeScore'] == 2
    assert payload['matches'][0]['awayScore'] == 1
    assert payload['matches'][1]['homeScore'] is None


def test_league_contract_returns_metadata_teams_ranking_and_real_matches() -> None:
    database = MemoryDatabase(
        support_leagues=MemoryCollection(
            [
                {
                    'league_key': 'league-a',
                    'league_name': 'League A',
                    'country': 'SE',
                    'season_id': 2026,
                    'captured_at': datetime(2026, 8, 12, 18, tzinfo=UTC),
                }
            ]
        ),
        support_teams=MemoryCollection(
            [
                {
                    'team_key': 'team-home',
                    'league_key': 'league-a',
                    'team_name': 'Home FC',
                    'team_image_url': 'https://example.invalid/home.png',
                    'opta_rank': 22,
                    'opta_rating': 81.2,
                    'captured_at': datetime(2026, 8, 12, 18, tzinfo=UTC),
                }
            ]
        ),
        support_rankings=MemoryCollection(
            [
                {
                    'league_key': 'league-a',
                    'league_name': 'League A',
                    'ranking_type': 'league_support',
                    'league_avg_opta_rating': 78.4,
                    'ranking': {'source': 'stored-ranking'},
                    'captured_at': datetime(2026, 8, 12, 18, tzinfo=UTC),
                }
            ]
        ),
        fixtures_canonical=MemoryCollection([fixture('m1')]),
        match_results_canonical=MemoryCollection(),
    )

    payload = read_service.read_league(database, 'league-a')

    assert payload is not None
    assert payload['league']['leagueKey'] == 'league-a'
    assert payload['league']['country'] == 'SE'
    assert payload['teams'][0]['teamKey'] == 'team-home'
    assert payload['ranking']['leagueAverageOptaRating'] == 78.4
    assert payload['ranking']['data'] == {'source': 'stored-ranking'}
    assert payload['matches'][0]['matchKey'] == 'm1'


def test_team_contract_exposes_explicit_home_away_profiles_and_entity_references() -> None:
    database = MemoryDatabase(
        support_teams=MemoryCollection(
            [
                {
                    'team_key': 'team-home',
                    'league_key': 'league-a',
                    'team_name': 'Home FC',
                    'team_image_url': 'https://example.invalid/home.png',
                    'opta_rank': 22,
                    'opta_rating': 81.2,
                    'captured_at': datetime(2026, 8, 12, 18, tzinfo=UTC),
                }
            ]
        ),
        support_leagues=MemoryCollection(
            [{'league_key': 'league-a', 'league_name': 'League A', 'country': 'SE'}]
        ),
        teamprofiles=MemoryCollection(
            [team_profile('team-home', 'home', 13.0), team_profile('team-home', 'away', 11.0)]
        ),
        fixtures_canonical=MemoryCollection(
            [
                fixture('next', home_key='team-home', home_name='Home FC'),
                fixture(
                    'other',
                    home_key='other-home',
                    away_key='team-home',
                    home_name='Other FC',
                    away_name='Home FC',
                ),
            ]
        ),
        match_results_canonical=MemoryCollection(),
    )

    payload = read_service.read_team(database, 'team-home')

    assert payload is not None
    assert payload['team']['teamKey'] == 'team-home'
    assert payload['league']['leagueKey'] == 'league-a'
    assert payload['contexts']['home']['matchType'] == 'home'
    assert payload['contexts']['away']['matchType'] == 'away'
    assert payload['contexts']['home']['statistics']['for']['fouls']['ALL']['value'] == 13.0
    assert payload['contexts']['home']['statistics']['against']['fouls']['ALL']['value'] == 12.0
    assert payload['contexts']['home']['games'][0]['matchKey'] == 'past-77'
    assert payload['contexts']['home']['games'][0]['opponentTeamKey'] == 'opponent'
    assert {row['matchKey'] for row in payload['matches']} == {'next', 'other'}


def test_match_detail_includes_canonical_result_actual_stats_and_market_offers() -> None:
    database = MemoryDatabase(
        fixtures_canonical=MemoryCollection([fixture('m1')]),
        matchups_score=MemoryCollection(),
        matchups_league_avg=MemoryCollection(),
        market_snapshots=MemoryCollection(),
        market_offers=MemoryCollection(
            [
                {
                    'offer_key': 'offer-1',
                    'match_key': 'm1',
                    'event_id': 'event-1',
                    'stat_key': 'fouls',
                    'scope': 'away',
                    'period': 'ALL',
                    'line': 12.5,
                    'over_odds': 1.9,
                    'under_odds': 1.8,
                    'source_provider': 'kambi',
                    'payload_kind': 'kambi',
                    'updated_at': datetime(2026, 8, 13, 15, tzinfo=UTC),
                }
            ]
        ),
        match_results_canonical=MemoryCollection(
            [
                {
                    'match_key': 'm1',
                    'home_score': 1,
                    'away_score': 2,
                    'fetched_at': datetime(2026, 8, 13, 21, tzinfo=UTC),
                    'mapping_confidence': 'exact',
                }
            ]
        ),
        match_stats_canonical=MemoryCollection(
            [
                {
                    'match_key': 'm1',
                    'stat_key': 'fouls',
                    'period': 'ALL',
                    'scope': 'away',
                    'actual_value': 14,
                    'mapping_confidence': 'exact',
                }
            ]
        ),
        teamprofiles=MemoryCollection(),
    )

    payload = read_service.read_match_detail(database, 'm1')

    assert payload is not None
    assert payload['result']['homeScore'] == 1
    assert payload['result']['awayScore'] == 2
    assert payload['actualStats'][0] == {
        'statKey': 'fouls',
        'period': 'ALL',
        'scope': 'away',
        'actualValue': 14,
        'mappingConfidence': 'exact',
    }
    assert payload['marketOffers'][0]['offerKey'] == 'offer-1'
    assert payload['marketOffers'][0]['line'] == 12.5
    assert payload['marketOffers'][0]['overOdds'] == 1.9
    assert payload['marketOffers'][0]['sourceProvider'] == 'kambi'
    assert payload['marketOffers'][0]['modelSupport'] == 'model_missing'
    assert payload['marketOffers'][0]['modelSupportReason'] == 'stat_key_not_trained'
    assert payload['marketOffers'][0]['supportedDirections'] == []


def test_market_offer_contract_distinguishes_full_partial_and_missing_model_support() -> None:
    corners = read_service._market_offer_summary(
        {'stat_key': 'cornerKicks', 'scope': 'total', 'period': 'ALL'}
    )
    shots = read_service._market_offer_summary(
        {'stat_key': 'shotsOnGoal', 'scope': 'home', 'period': '1ST'}
    )
    unsupported = read_service._market_offer_summary(
        {'stat_key': 'fouls', 'scope': 'away', 'period': 'ALL'}
    )

    assert corners['modelSupport'] == 'supported'
    assert corners['supportedDirections'] == ['over', 'under']
    assert shots['modelSupport'] == 'partially_supported'
    assert shots['supportedDirections'] == ['over']
    assert unsupported['modelSupport'] == 'model_missing'


def test_auto_contract_filters_counts_and_paginates_before_frontend_rendering() -> None:
    database = MemoryDatabase(
        forward_bets=MemoryCollection(
            [
                {
                    'selection_key': 's1',
                    'match_key': 'm1',
                    'stat_key': 'fouls',
                    'period': 'ALL',
                    'scope': 'away',
                    'direction': 'over',
                    'valid_for_forward_evaluation': True,
                    'invalid_for_model': False,
                    'match_start_time': datetime(2026, 8, 15, 12, tzinfo=UTC),
                },
                {
                    'selection_key': 's2',
                    'match_key': 'm2',
                    'stat_key': 'fouls',
                    'period': 'ALL',
                    'scope': 'home',
                    'direction': 'under',
                    'valid_for_forward_evaluation': False,
                    'invalid_for_model': True,
                    'match_start_time': datetime(2026, 8, 14, 12, tzinfo=UTC),
                },
                {
                    'selection_key': 's3',
                    'match_key': 'm3',
                    'stat_key': 'offsides',
                    'period': 'ALL',
                    'scope': 'home',
                    'direction': 'over',
                    'valid_for_forward_evaluation': True,
                    'invalid_for_model': False,
                    'match_start_time': datetime(2026, 8, 13, 12, tzinfo=UTC),
                },
            ]
        ),
        fixtures_canonical=MemoryCollection(
            [
                fixture('m1', home_key='h1', away_key='a1'),
                fixture('m2', home_key='h2', away_key='a2'),
                fixture('m3', home_key='h3', away_key='a3'),
            ]
        ),
    )

    payload = read_service.read_auto(database, stat_key='fouls', limit=1, offset=1)

    assert {
        key: payload['summary'][key]
        for key in (
            'total', 'groups', 'valid', 'excluded', 'acceptedClvCount',
            't30ClvCount', 't10ClvCount', 'beatClosingLineCount',
            'averageAcceptedClvPct',
        )
    } == {
        'total': 2,
        'groups': 2,
        'valid': 1,
        'excluded': 1,
        'acceptedClvCount': 0,
        't30ClvCount': 0,
        't10ClvCount': 0,
        'beatClosingLineCount': 0,
        'averageAcceptedClvPct': None,
    }
    assert payload['summary']['open'] == 1
    assert payload['summary']['openGroups'] == 1
    assert payload['summary']['settled'] == 0
    assert payload['summary']['byFamily']['legacy']['total'] == 2
    assert payload['summary']['byFamily']['v6']['total'] == 0
    assert payload['page'] == {'limit': 1, 'offset': 1, 'hasMore': False}
    assert [row['selectionKey'] for row in payload['selections']] == ['s2']
    assert payload['selections'][0]['homeTeamKey'] == 'h2'
    assert payload['selections'][0]['leagueKey'] == 'league-a'


def test_auto_groups_checkpoint_rows_after_filtering_and_keeps_observation_totals() -> None:
    shared = {
        'prediction_type': 'ev_registered_score_policy',
        'model_id': 'ev_scope_interaction_recency45_asof_capped_v6_shadow',
        'selection_policy_id': 'v6_full_domain_checkpoint_journal_v2',
        'selection_granularity': 'checkpoint_observation',
        'match_key': 'm1',
        'stat_key': 'cornerKicks',
        'period': 'ALL',
        'scope': 'total',
        'direction': 'over',
        'line_value': 10.5,
        'stake_units': 1.0,
        'valid_for_forward_evaluation': True,
        'invalid_for_model': False,
        'match_start_time': datetime(2026, 8, 15, 12, tzinfo=UTC),
    }
    database = MemoryDatabase(
        forward_bets=MemoryCollection(
            [
                shared | {
                    'prediction_key': 'p-t3d',
                    'selection_key': 'p-t3d',
                    'snapshot_key': 's-t3d',
                    'snapshot_label': 'T_MINUS_3D',
                    'expected_roi_units': 0.08,
                },
                shared | {
                    'prediction_key': 'p-t2h',
                    'selection_key': 'p-t2h',
                    'snapshot_key': 's-t2h',
                    'snapshot_label': 'T_MINUS_2H',
                    'expected_roi_units': 0.12,
                },
            ]
        ),
        forward_results=MemoryCollection(
            [
                {
                    **shared,
                    'result_loop_key': 'p-t3d',
                    'prediction_key': 'p-t3d',
                    'snapshot_label': 'T_MINUS_3D',
                    'expected_roi_units': 0.08,
                    'settlement_status': 'settled',
                    'settlement_result': 'win',
                    'pnl_units': 0.9,
                    'official_clv': True,
                    'beat_closing_line': True,
                    'clv_pct': 4.0,
                    'valid_for_performance': True,
                },
                {
                    **shared,
                    'result_loop_key': 'p-t2h',
                    'prediction_key': 'p-t2h',
                    'snapshot_label': 'T_MINUS_2H',
                    'expected_roi_units': 0.12,
                    'settlement_status': 'settled',
                    'settlement_result': 'win',
                    'pnl_units': 1.1,
                    'official_clv': True,
                    'beat_closing_line': False,
                    'clv_pct': -2.0,
                    'valid_for_performance': True,
                },
            ]
        ),
        fixtures_canonical=MemoryCollection([fixture('m1')]),
    )

    payload = read_service.read_auto(database)

    assert payload['summary']['total'] == 2
    assert payload['summary']['groups'] == 1
    assert payload['count'] == 1
    assert len(payload['selections']) == 1
    row = payload['selections'][0]
    assert row['selectionKey'] == 'p-t2h'
    assert row['observationCount'] == 2
    assert row['checkpointLabels'] == ['T_MINUS_3D', 'T_MINUS_2H']
    assert row['bestCheckpointLabel'] == 'T_MINUS_2H'
    assert row['stakeUnits'] == 2.0
    assert row['pnlUnits'] == 2.0
    assert row['roiUnits'] == 1.0
    assert row['officialClvCount'] == 2
    assert row['beatClosingLineCount'] == 1

    filtered = read_service.read_auto(database, checkpoint='T_MINUS_3D')

    assert filtered['summary']['total'] == 1
    assert filtered['summary']['groups'] == 1
    assert filtered['selections'][0]['selectionKey'] == 'p-t3d'
    assert filtered['selections'][0]['observationCount'] == 1


def test_auto_exposes_accepted_t30_clv_and_exact_market_odds_history() -> None:
    shared = {
        'prediction_type': 'ev_registered_score_policy',
        'model_id': 'ev_scope_interaction_recency45_asof_capped_v6_shadow',
        'selection_policy_id': 'v6_full_domain_checkpoint_journal_v2',
        'selection_granularity': 'checkpoint_observation',
        'prediction_key': 'p-t3d',
        'selection_key': 'p-t3d',
        'match_key': 'm1',
        'offer_key': 'offer-exact',
        'stat_key': 'cornerKicks',
        'period': 'ALL',
        'scope': 'total',
        'direction': 'over',
        'line_value': 10.5,
        'snapshot_label': 'T_MINUS_3D',
        'selected_odds': 1.95,
        'valid_for_forward_evaluation': True,
        'invalid_for_model': False,
        'match_start_time': datetime(2026, 8, 15, 12, tzinfo=UTC),
    }
    database = MemoryDatabase(
        forward_bets=MemoryCollection([shared]),
        forward_results=MemoryCollection(
            [
                shared | {
                    'result_loop_key': 'p-t3d',
                    'settlement_status': 'settled',
                    'settlement_result': 'win',
                    'valid_for_performance': True,
                    'accepted_clv': True,
                    'eligible_for_promotion_clv': False,
                    'official_clv': False,
                    'closing_quality': 't30_fallback',
                    'closing_checkpoint': 'T_MINUS_30M',
                    'closing_snapshot_label': 'T_MINUS_30M',
                    'closing_odds': 1.8,
                    'clv_status': 'tracked_fallback_t30',
                    'clv_pct': 8.3,
                    'beat_closing_line': True,
                    'price_history': [
                        {
                            'snapshot_label': 'T_MINUS_3D',
                            'observed_at': '2026-08-12T12:00:00Z',
                            'odds': 1.95,
                            'line_value': 10.5,
                            'direction': 'over',
                        },
                        {
                            'snapshot_label': 'T_MINUS_2H',
                            'observed_at': '2026-08-15T10:00:00Z',
                            'odds': 1.88,
                            'line_value': 10.5,
                            'direction': 'over',
                        },
                        {
                            'snapshot_label': 'T_MINUS_30M',
                            'observed_at': '2026-08-15T11:30:00Z',
                            'odds': 1.8,
                            'line_value': 10.5,
                            'direction': 'over',
                        },
                        {
                            'snapshot_label': 'T_MINUS_30M',
                            'observed_at': '2026-08-15T11:30:00Z',
                            'odds': 2.0,
                            'line_value': 11.5,
                            'direction': 'over',
                        },
                        {
                            'snapshot_label': 'T_MINUS_30M',
                            'observed_at': '2026-08-15T11:30:00Z',
                            'odds': 2.05,
                            'line_value': 10.5,
                            'direction': 'under',
                        },
                    ],
                }
            ]
        ),
        fixtures_canonical=MemoryCollection([fixture('m1')]),
    )

    payload = read_service.read_auto(database)

    assert payload['summary']['acceptedClvCount'] == 1
    assert payload['summary']['t30ClvCount'] == 1
    assert payload['summary']['t10ClvCount'] == 0
    assert payload['summary']['beatClosingLineCount'] == 1
    assert payload['summary']['averageAcceptedClvPct'] == 8.3
    row = payload['selections'][0]
    assert row['acceptedClv'] is True
    assert row['officialClv'] is False
    assert row['closingStatus'] == 'accepted'
    assert row['closingQuality'] == 't30_fallback'
    assert row['closingCheckpoint'] == 'T_MINUS_30M'
    assert row['closingOdds'] == 1.8
    assert row['clvPct'] == 8.3
    assert row['clvDistancePct'] == 8.3
    assert row['beatClosingLine'] is True
    assert row['acceptedClvCount'] == 1
    assert row['oddsHistory'] == [
        {
            'snapshotLabel': 'T_MINUS_3D',
            'observedAt': '2026-08-12T12:00:00Z',
            'odds': 1.95,
            'lineValue': 10.5,
            'selected': True,
            'closing': False,
        },
        {
            'snapshotLabel': 'T_MINUS_2H',
            'observedAt': '2026-08-15T10:00:00Z',
            'odds': 1.88,
            'lineValue': 10.5,
            'selected': False,
            'closing': False,
        },
        {
            'snapshotLabel': 'T_MINUS_30M',
            'observedAt': '2026-08-15T11:30:00Z',
            'odds': 1.8,
            'lineValue': 10.5,
            'selected': False,
            'closing': True,
        },
    ]


def test_auto_status_filter_is_applied_before_grouping_and_pagination() -> None:
    base = {
        'match_key': 'm1',
        'stat_key': 'cornerKicks',
        'period': 'ALL',
        'scope': 'total',
        'direction': 'over',
        'line_value': 10.5,
        'valid_for_forward_evaluation': True,
        'invalid_for_model': False,
    }
    database = MemoryDatabase(
        forward_bets=MemoryCollection(
            [
                base | {'selection_key': 'open'},
                base | {
                    'selection_key': 'won',
                    'line_value': 11.5,
                    'prediction_type': 'ev_registered_score_policy',
                    'selection_policy_id': 'v6_full_domain_checkpoint_journal_v2',
                    'model_id': 'ev_scope_interaction_recency45_asof_capped_v6_shadow',
                },
                base | {'selection_key': 'lost', 'line_value': 12.5},
                base | {'selection_key': 'excluded', 'line_value': 13.5},
            ]
        ),
        forward_results=MemoryCollection(
            [
                base | {
                    'result_loop_key': 'won',
                    'selection_key': 'won',
                    'line_value': 11.5,
                    'settlement_status': 'settled',
                    'settlement_result': 'win',
                    'valid_for_performance': True,
                    'stake_units': 1.0,
                    'pnl_units': 1.0,
                },
                base | {
                    'result_loop_key': 'lost',
                    'selection_key': 'lost',
                    'line_value': 12.5,
                    'settlement_status': 'settled',
                    'settlement_result': 'loss',
                    'valid_for_performance': True,
                    'stake_units': 1.0,
                    'pnl_units': -1.0,
                },
                base | {
                    'result_loop_key': 'excluded',
                    'selection_key': 'excluded',
                    'line_value': 13.5,
                    'result_loop_status': 'excluded',
                    'valid_for_performance': False,
                },
            ]
        ),
    )

    settled = read_service.read_auto(database, status='settled', limit=1)
    won = read_service.read_auto(database, status='win')
    opened = read_service.read_auto(database, status='open')
    excluded = read_service.read_auto(database, status='excluded')

    assert settled['summary']['total'] == 2
    assert settled['count'] == 2
    assert settled['page']['hasMore'] is True
    assert settled['summary']['settled'] == 2
    assert settled['summary']['wins'] == 1
    assert settled['summary']['losses'] == 1
    assert settled['summary']['pushes'] == 0
    assert settled['summary']['stakeUnits'] == 2.0
    assert settled['summary']['pnlUnits'] == 0.0
    assert settled['summary']['roiPct'] == 0.0
    assert settled['summary']['byFamily']['v6']['settled'] == 1
    assert settled['summary']['byFamily']['legacy']['settled'] == 1
    assert won['summary']['total'] == 1
    assert won['selections'][0]['selectionKey'] == 'won'
    assert opened['summary']['total'] == 1
    assert opened['selections'][0]['selectionKey'] == 'open'
    assert excluded['summary']['total'] == 1
    assert excluded['selections'][0]['selectionKey'] == 'excluded'


def test_results_contract_is_typed_filtered_paginated_and_entity_joined() -> None:
    database = MemoryDatabase(
        forward_results=MemoryCollection(
            [
                {
                    'result_loop_key': 'r1',
                    'prediction_key': 'p1',
                    'match_key': 'm1',
                    'stat_key': 'fouls',
                    'period': 'ALL',
                    'scope': 'away',
                    'direction': 'over',
                    'line_value': 12.5,
                    'saved_odds': 1.9,
                    'settlement_status': 'settled',
                    'settlement_result': 'win',
                    'actual_value': 14,
                    'win': True,
                    'roi_units': 0.9,
                    'pnl_units': 0.9,
                    'valid_for_performance': True,
                    'clv_status': 'available',
                    'closing_quality': 't10',
                    'official_clv': True,
                    'closing_odds': 1.8,
                    'clv_pct': 5.5,
                    'result_loop_status': 'settled',
                    'match_start_time': datetime(2026, 8, 13, 18, tzinfo=UTC),
                },
                {
                    'result_loop_key': 'r2',
                    'prediction_key': 'p2',
                    'match_key': 'm2',
                    'stat_key': 'offsides',
                    'settlement_status': 'invalid_timing',
                    'valid_for_performance': False,
                    'result_loop_status': 'excluded',
                    'status_reason': 'snapshot_at_or_after_match_start',
                    'match_start_time': datetime(2026, 8, 12, 18, tzinfo=UTC),
                },
            ]
        ),
        fixtures_canonical=MemoryCollection(
            [
                fixture('m1', home_key='h1', away_key='a1'),
                fixture('m2', home_key='h2', away_key='a2'),
            ]
        ),
    )

    payload = read_service.read_results(database, status='settled', limit=1, offset=0)

    assert payload['summary'] == {
        'rows': 1,
        'groups': 1,
        'settled': 1,
        'wins': 1,
        'losses': 0,
        'pushes': 0,
        'excluded': 0,
        'stakeUnits': 0,
        'pnlUnits': 0.9,
        'roiPct': None,
        'officialClvObservations': 1,
        'beatClosingLine': 0,
        'clvBeatRatePct': 0.0,
    }
    assert payload['page'] == {'limit': 1, 'offset': 0, 'hasMore': False}
    row = payload['rows'][0]
    assert row['resultLoopKey'] == 'r1'
    assert row['matchKey'] == 'm1'
    assert row['homeTeamKey'] == 'h1'
    assert row['awayTeamKey'] == 'a1'
    assert row['settlementResult'] == 'win'
    assert row['officialClv'] is True
    assert row['clvPct'] == 5.5
    assert 'result_loop_key' not in row


def test_results_group_rows_but_calculate_roi_and_clv_over_every_observation() -> None:
    shared = {
        'prediction_type': 'ev_registered_score_policy',
        'model_id': 'ev_scope_interaction_recency45_asof_capped_v6_shadow',
        'selection_policy_id': 'v6_full_domain_checkpoint_journal_v2',
        'selection_granularity': 'checkpoint_observation',
        'match_key': 'm1',
        'stat_key': 'cornerKicks',
        'period': 'ALL',
        'scope': 'total',
        'direction': 'over',
        'line_value': 10.5,
        'settlement_status': 'settled',
        'settlement_result': 'win',
        'valid_for_performance': True,
        'official_clv': True,
        'stake_units': 1.0,
        'result_loop_status': 'settled',
        'match_start_time': datetime(2026, 8, 13, 18, tzinfo=UTC),
    }
    database = MemoryDatabase(
        forward_results=MemoryCollection(
            [
                shared | {
                    'result_loop_key': 'p-t3d',
                    'prediction_key': 'p-t3d',
                    'snapshot_label': 'T_MINUS_3D',
                    'expected_roi_units': 0.08,
                    'pnl_units': 0.9,
                    'beat_closing_line': True,
                    'clv_pct': 4.0,
                },
                shared | {
                    'result_loop_key': 'p-t2h',
                    'prediction_key': 'p-t2h',
                    'snapshot_label': 'T_MINUS_2H',
                    'expected_roi_units': 0.12,
                    'pnl_units': 1.1,
                    'beat_closing_line': False,
                    'clv_pct': -2.0,
                },
            ]
        ),
        fixtures_canonical=MemoryCollection([fixture('m1')]),
    )

    payload = read_service.read_results(database)

    assert payload['summary']['rows'] == 2
    assert payload['summary']['groups'] == 1
    assert payload['summary']['stakeUnits'] == 2.0
    assert payload['summary']['pnlUnits'] == 2.0
    assert payload['summary']['roiPct'] == 100.0
    assert payload['summary']['officialClvObservations'] == 2
    assert payload['summary']['beatClosingLine'] == 1
    assert payload['summary']['clvBeatRatePct'] == 50.0
    assert len(payload['rows']) == 1
    row = payload['rows'][0]
    assert row['predictionKey'] == 'p-t2h'
    assert row['observationCount'] == 2
    assert row['stakeUnits'] == 2.0
    assert row['pnlUnits'] == 2.0
    assert row['averageClvPct'] == 1.0


def test_http_auto_and_results_routes_forward_checkpoint_filter() -> None:
    database = MemoryDatabase(
        forward_bets=MemoryCollection(
            [
                {
                    'selection_key': 't3d',
                    'match_key': 'm1',
                    'snapshot_label': 'T_MINUS_3D',
                },
                {
                    'selection_key': 't2h',
                    'match_key': 'm1',
                    'snapshot_label': 'T_MINUS_2H',
                },
            ]
        ),
        forward_results=MemoryCollection(
            [
                {
                    'result_loop_key': 't3d',
                    'match_key': 'm1',
                    'snapshot_label': 'T_MINUS_3D',
                },
                {
                    'result_loop_key': 't2h',
                    'match_key': 'm1',
                    'snapshot_label': 'T_MINUS_2H',
                },
            ]
        ),
    )

    auto_status, auto_payload = read_http.dispatch_get(
        database,
        '/api/v1/auto',
        {'checkpoint': ['T_MINUS_2H'], 'status': ['open']},
    )
    result_status, result_payload = read_http.dispatch_get(
        database,
        '/api/v1/results',
        {'checkpoint': ['T_MINUS_3D']},
    )

    assert auto_status.value == 200
    assert auto_payload['summary']['total'] == 1
    assert auto_payload['selections'][0]['selectionKey'] == 't2h'
    assert result_status.value == 200
    assert result_payload['summary']['rows'] == 1
    assert result_payload['rows'][0]['resultLoopKey'] == 't3d'


def test_http_dispatch_exposes_resolver_and_league_routes_without_mutations() -> None:
    database = MemoryDatabase(
        fixtures_canonical=MemoryCollection([fixture('m1')]),
        match_results_canonical=MemoryCollection(),
        support_leagues=MemoryCollection([{'league_key': 'league-a', 'league_name': 'League A'}]),
        support_teams=MemoryCollection(),
        support_rankings=MemoryCollection(),
    )

    status, match_payload = read_http.dispatch_get(database, '/api/v1/matches', {'key': ['m1']})
    assert status.value == 200
    assert match_payload['matches'][0]['matchKey'] == 'm1'

    status, league_payload = read_http.dispatch_get(database, '/api/v1/leagues/league-a', {})
    assert status.value == 200
    assert league_payload['league']['leagueKey'] == 'league-a'
