from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.line_history import (
    build_asof_line_history_features,
    build_line_history_features,
)


def test_line_history_excludes_current_and_future_matches() -> None:
    markets = pd.DataFrame(
        [
            {
                "sample_key": "current|cornerKicks|ALL|home",
                "kickoff_ts": 300,
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "home",
                "line_value": 5.5,
                "over_odds": 1.9,
                "under_odds": 1.9,
            }
        ]
    )
    team_stats = pd.DataFrame(
        [
            {
                "match_id": "past-a",
                "kickoff_ts": 100,
                "team_name": "Arsenal",
                "team_role": "home",
                "stat_item_key": "cornerKicks",
                "period": "ALL",
                "team_value": 7.0,
                "opponent_value": 3.0,
                "total_value": 10.0,
            },
            {
                "match_id": "past-b",
                "kickoff_ts": 200,
                "team_name": "Chelsea",
                "team_role": "away",
                "stat_item_key": "cornerKicks",
                "period": "ALL",
                "team_value": 2.0,
                "opponent_value": 6.0,
                "total_value": 8.0,
            },
            {
                "match_id": "current",
                "kickoff_ts": 300,
                "team_name": "Arsenal",
                "team_role": "home",
                "stat_item_key": "cornerKicks",
                "period": "ALL",
                "team_value": 99.0,
                "opponent_value": 0.0,
                "total_value": 99.0,
            },
            {
                "match_id": "future",
                "kickoff_ts": 400,
                "team_name": "Arsenal",
                "team_role": "home",
                "stat_item_key": "cornerKicks",
                "period": "ALL",
                "team_value": 99.0,
                "opponent_value": 0.0,
                "total_value": 99.0,
            },
        ]
    )

    features = build_line_history_features(
        markets,
        team_stats,
        windows=(10,),
        prior_strength=2.0,
    )

    row = features.iloc[0]
    assert row["line_history_role_attack_n_10"] == 1
    assert row["line_history_role_defense_n_10"] == 1
    assert row["line_history_role_attack_rate_10"] == pytest.approx(1.0)
    assert row["line_history_role_defense_rate_10"] == pytest.approx(1.0)
    assert row["line_history_role_combined_n_10"] == 2
    assert row["line_history_role_posterior_over_10"] == pytest.approx(0.75)


def test_line_history_deduplicates_same_past_match_between_teams() -> None:
    markets = pd.DataFrame(
        [
            {
                "sample_key": "current|cornerKicks|ALL|total",
                "kickoff_ts": 300,
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 9.5,
                "over_odds": 1.9,
                "under_odds": 1.9,
            }
        ]
    )
    team_stats = pd.DataFrame(
        [
            {
                "match_id": "head-to-head",
                "kickoff_ts": 100,
                "team_name": "Arsenal",
                "team_role": "home",
                "stat_item_key": "cornerKicks",
                "period": "ALL",
                "team_value": 6.0,
                "opponent_value": 5.0,
                "total_value": 11.0,
            },
            {
                "match_id": "head-to-head",
                "kickoff_ts": 100,
                "team_name": "Chelsea",
                "team_role": "away",
                "stat_item_key": "cornerKicks",
                "period": "ALL",
                "team_value": 5.0,
                "opponent_value": 6.0,
                "total_value": 11.0,
            },
        ]
    )

    features = build_line_history_features(
        markets,
        team_stats,
        windows=(10,),
    )

    assert features.iloc[0]["line_history_all_combined_n_10"] == 1


def test_total_shots_uses_total_shots_on_goal_history() -> None:
    markets = pd.DataFrame(
        [
            {
                "sample_key": "current|totalShots|ALL|home",
                "kickoff_ts": 300,
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "stat_key": "totalShots",
                "period": "ALL",
                "scope": "home",
                "line_value": 10.5,
                "over_odds": 1.8,
                "under_odds": None,
            }
        ]
    )
    team_stats = pd.DataFrame(
        [
            {
                "match_id": "past",
                "kickoff_ts": 100,
                "team_name": "Arsenal",
                "team_role": "home",
                "stat_item_key": "totalShotsOnGoal",
                "period": "ALL",
                "team_value": 12.0,
                "opponent_value": 8.0,
                "total_value": 20.0,
            }
        ]
    )

    features = build_line_history_features(
        markets,
        team_stats,
        windows=(10,),
    )

    assert features.iloc[0]["line_history_all_attack_rate_10"] == 1.0


def test_asof_line_history_excludes_stats_unavailable_at_snapshot() -> None:
    markets = pd.DataFrame(
        [
            {
                "sample_key": "current|cornerKicks|ALL|home",
                "kickoff_ts": 1_000,
                "odds_snapshot_time": pd.Timestamp(
                    500,
                    unit="s",
                    tz="UTC",
                ),
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "home",
                "line_value": 5.5,
                "over_odds": 1.9,
                "under_odds": 1.9,
            }
        ]
    )
    team_stats = pd.DataFrame(
        [
            {
                "match_id": "available",
                "kickoff_ts": 100,
                "team_name": "Arsenal",
                "team_role": "home",
                "stat_item_key": "cornerKicks",
                "period": "ALL",
                "team_value": 7.0,
                "opponent_value": 3.0,
                "total_value": 10.0,
            },
            {
                "match_id": "not-yet-available",
                "kickoff_ts": 200,
                "team_name": "Arsenal",
                "team_role": "home",
                "stat_item_key": "cornerKicks",
                "period": "ALL",
                "team_value": 8.0,
                "opponent_value": 2.0,
                "total_value": 10.0,
            },
        ]
    )

    features, audit = build_asof_line_history_features(
        markets,
        team_stats,
        windows=(10,),
        availability_buffer_hours=0.1,
    )

    assert features.iloc[0]["line_history_role_attack_n_10"] == 1
    assert features.iloc[0]["line_history_role_attack_rate_10"] == 1.0
    assert audit["history_observations_at_or_after_snapshot_used"] == 0
    assert audit["history_observations_excluded_by_snapshot"] >= 1
