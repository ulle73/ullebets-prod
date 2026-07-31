from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.engineering import (
    build_compact_model_features,
    build_context_model_features,
    build_horizon_model_features,
)


def test_total_scope_combines_both_attacks_and_defenses() -> None:
    frame = pd.DataFrame(
        {
            "stat_key": ["shotsOnGoal"],
            "scope": ["total"],
            "period": ["ALL"],
            "league_name_normalized": ["Premier League"],
            "line_value": [9.5],
            "over_odds": [2.0],
            "under_odds": [None],
            "baseline_lambda": [9.0],
            "latest_snapshot_minutes_before_kickoff": [120.0],
            "home__shotsOnGoal__team_for_role_avg_10": [6.0],
            "away__shotsOnGoal__team_against_role_avg_10": [5.0],
            "away__shotsOnGoal__team_for_role_avg_10": [4.0],
            "home__shotsOnGoal__team_against_role_avg_10": [3.0],
        }
    )

    features = build_compact_model_features(frame, windows=(10,))

    assert features.iloc[0]["history_role_expected_10"] == pytest.approx(9.0)
    assert features.iloc[0]["history_role_attack_10"] == pytest.approx(10.0)
    assert features.iloc[0]["history_role_defense_10"] == pytest.approx(8.0)
    assert features.iloc[0]["snapshot_lead_hours"] == pytest.approx(2.0)


def test_total_shots_uses_total_shots_on_goal_history_key() -> None:
    frame = pd.DataFrame(
        {
            "stat_key": ["totalShots"],
            "scope": ["home"],
            "period": ["ALL"],
            "league_name_normalized": ["Serie A"],
            "line_value": [14.5],
            "over_odds": [1.9],
            "under_odds": [None],
            "baseline_lambda": [15.0],
            "home__totalShotsOnGoal__team_for_role_avg_5": [16.0],
            "away__totalShotsOnGoal__team_against_role_avg_5": [14.0],
        }
    )

    features = build_compact_model_features(frame, windows=(5,))

    assert features.iloc[0]["history_role_expected_5"] == pytest.approx(15.0)


def test_compact_features_never_copy_target_or_current_match_values() -> None:
    frame = pd.DataFrame(
        {
            "stat_key": ["cornerKicks"],
            "scope": ["home"],
            "period": ["ALL"],
            "league_name_normalized": ["La Liga"],
            "line_value": [5.5],
            "over_odds": [1.9],
            "under_odds": [1.9],
            "actual_value": [8.0],
            "home__cornerKicks__team_value": [8.0],
            "home__cornerKicks__team_for_role_avg_5": [5.0],
            "away__cornerKicks__team_against_role_avg_5": [4.0],
        }
    )

    features = build_compact_model_features(frame, windows=(5,))

    assert "actual_value" not in features
    assert not any("team_value" in column for column in features)


def test_context_features_use_only_shifted_history_columns() -> None:
    frame = pd.DataFrame(
        {
            "stat_key": ["cornerKicks"],
            "scope": ["home"],
            "period": ["ALL"],
            "league_name_normalized": ["La Liga"],
            "line_value": [5.5],
            "over_odds": [1.9],
            "under_odds": [1.9],
            "actual_value": [8.0],
            "home_opta_rating": [92.0],
            "home__expectedGoals__team_for_all_avg_10": [1.8],
            "away__shotsOnGoal__team_against_role_avg_5": [6.0],
            "home__cornerKicks__team_value": [8.0],
            "home__cornerKicks__team_for_role_avg_10": [5.0],
            "away__cornerKicks__team_against_role_avg_10": [4.0],
        }
    )

    features = build_context_model_features(frame, windows=(5, 10))

    assert (
        features.iloc[0]["context_expectedGoals_all_home_for_10"]
        == pytest.approx(1.8)
    )
    assert (
        features.iloc[0]["context_shotsOnGoal_role_away_against_5"]
        == pytest.approx(6.0)
    )
    assert "actual_value" not in features
    assert "home_opta_rating" not in features
    assert not any("team_value" in column for column in features)


def test_horizon_features_use_predefined_operational_time_buckets() -> None:
    frame = pd.DataFrame(
        {
            "stat_key": ["cornerKicks"] * 5,
            "scope": ["total"] * 5,
            "period": ["ALL"] * 5,
            "league_name_normalized": ["La Liga"] * 5,
            "line_value": [10.5] * 5,
            "over_odds": [1.9] * 5,
            "under_odds": [1.9] * 5,
            "latest_snapshot_minutes_before_kickoff": [
                10.0,
                120.0,
                720.0,
                2_880.0,
                4_320.0,
            ],
        }
    )

    features = build_horizon_model_features(frame, windows=())

    assert features["snapshot_horizon_bucket"].tolist() == [
        "LT_15M",
        "H1_TO_3H",
        "H12_TO_18H",
        "H36_TO_60H",
        "H60_TO_84H",
    ]
    assert features["snapshot_horizon_log1p_hours"].tolist() == (
        pytest.approx(
            [
                0.1541506798,
                1.0986122887,
                2.5649493575,
                3.8918202981,
                4.2904594411,
            ]
        )
    )
