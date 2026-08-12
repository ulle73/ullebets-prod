from __future__ import annotations

from datetime import UTC, datetime

from tests.v2.test_read_api_contracts import MemoryCollection, MemoryDatabase, fixture, team_profile
from ullebets_v2.read_api.drilldowns import read_league, read_match_detail, read_team


def test_team_history_resolves_match_and_opponent_entities_from_canonical_fixtures() -> None:
    profile = team_profile('team-home', 'home', 13.0)
    profile['games'] = [{'matchId': 77, 'date': '2026-08-10', 'opp': 'Opponent FC'}]
    database = MemoryDatabase(
        support_teams=MemoryCollection([{'team_key': 'team-home', 'league_key': 'league-a', 'team_name': 'Home FC'}]),
        support_leagues=MemoryCollection([{'league_key': 'league-a', 'league_name': 'League A'}]),
        teamprofiles=MemoryCollection([profile]),
        fixtures_canonical=MemoryCollection([
            fixture('past-77', source_date='2026-08-10', home_key='team-home', away_key='opponent', home_name='Home FC', away_name='Opponent FC') | {'source_match_id': 77},
        ]),
        match_results_canonical=MemoryCollection([{'match_key': 'past-77', 'home_score': 2, 'away_score': 1}]),
    )
    payload = read_team(database, 'team-home')
    assert payload is not None
    game = payload['contexts']['home']['games'][0]
    assert game['matchKey'] == 'past-77'
    assert game['opponentTeamKey'] == 'opponent'
    assert game['opponentName'] == 'Opponent FC'
    assert game['homeScore'] == 2
    assert game['awayScore'] == 1


def test_league_exposes_compact_stat_rows_for_all_current_team_contexts() -> None:
    home = team_profile('team-home', 'home', 13.0)
    away = team_profile('team-away', 'away', 8.0)
    database = MemoryDatabase(
        support_leagues=MemoryCollection([{'league_key': 'league-a', 'league_name': 'League A'}]),
        support_teams=MemoryCollection([
            {'team_key': 'team-home', 'league_key': 'league-a', 'team_name': 'Home FC'},
            {'team_key': 'team-away', 'league_key': 'league-a', 'team_name': 'Away FC'},
        ]),
        support_rankings=MemoryCollection(), teamprofiles=MemoryCollection([home, away]), fixtures_canonical=MemoryCollection(), match_results_canonical=MemoryCollection(),
    )
    payload = read_league(database, 'league-a')
    assert payload is not None
    rows = payload['statRows']
    assert any(row == {'teamKey':'team-home','teamName':'Home FC','context':'home','orientation':'for','statKey':'fouls','period':'ALL','value':13.0,'rank':2,'leagueAverage':10.5} for row in rows)
    assert any(row['teamKey']=='team-away' and row['context']=='away' and row['orientation']=='against' and row['value']==7.0 for row in rows)


def test_match_detail_joins_forward_selections_and_results_without_recomputing_them() -> None:
    database = MemoryDatabase(
        fixtures_canonical=MemoryCollection([fixture('m1')]), matchups_score=MemoryCollection(), matchups_league_avg=MemoryCollection(), market_snapshots=MemoryCollection(), market_offers=MemoryCollection(), match_results_canonical=MemoryCollection(), match_stats_canonical=MemoryCollection(), teamprofiles=MemoryCollection(),
        forward_bets=MemoryCollection([{'selection_key':'s1','prediction_key':'p1','match_key':'m1','stat_key':'fouls','period':'ALL','scope':'away','direction':'over','line_value':12.5,'saved_odds':1.9,'predicted_win_probability':0.61,'expected_roi_units':0.159,'model_id':'v6','model_status':'forward_test_only','selection_policy_id':'policy-1','valid_for_forward_evaluation':True}]),
        forward_results=MemoryCollection([{'result_loop_key':'r1','selection_key':'s1','prediction_key':'p1','match_key':'m1','stat_key':'fouls','period':'ALL','scope':'away','direction':'over','line_value':12.5,'saved_odds':1.9,'settlement_status':'settled','settlement_result':'win','actual_value':14,'win':True,'pnl_units':0.9,'roi_units':0.9,'valid_for_performance':True,'result_loop_status':'settled','official_clv':True,'clv_status':'available','closing_quality':'t10','closing_odds':1.8,'clv_pct':5.5}]),
    )
    payload = read_match_detail(database, 'm1')
    assert payload is not None
    assert payload['forwardSelections'][0]['selectionKey'] == 's1'
    assert payload['forwardSelections'][0]['expectedRoiUnits'] == 0.159
    assert payload['forwardResults'][0]['resultLoopKey'] == 'r1'
    assert payload['forwardResults'][0]['actualValue'] == 14
    assert payload['forwardResults'][0]['officialClv'] is True
