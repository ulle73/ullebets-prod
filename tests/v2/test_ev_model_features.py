from __future__ import annotations

import pandas as pd

from ullebets_v2.ev_model.features import (
    build_leakage_safe_feature_columns,
    find_forbidden_feature_columns,
)


def test_feature_schema_rejects_current_match_outcomes() -> None:
    frame = pd.DataFrame(
        {
            "line_value": [10.5],
            "over_odds": [1.9],
            "baseline_lambda": [10.2],
            "home__cornerKicks__team_for_role_avg_10": [5.4],
            "away__cornerKicks__team_against_role_avg_10": [5.1],
            "home__cornerKicks__team_value": [7.0],
            "actual_value": [12.0],
            "over_result": ["win"],
            "league_name_normalized": ["Premier League"],
            "period": ["ALL"],
            "scope": ["total"],
            "stat_key": ["cornerKicks"],
        }
    )

    numeric, categorical = build_leakage_safe_feature_columns(frame)

    assert numeric == [
        "away__cornerKicks__team_against_role_avg_10",
        "baseline_lambda",
        "home__cornerKicks__team_for_role_avg_10",
        "line_value",
        "over_odds",
    ]
    assert categorical == [
        "league_name_normalized",
        "period",
        "scope",
        "stat_key",
    ]
    assert find_forbidden_feature_columns(frame.columns) == [
        "actual_value",
        "home__cornerKicks__team_value",
        "over_result",
    ]


def test_feature_schema_excludes_unversioned_support_ratings() -> None:
    frame = pd.DataFrame(
        {
            "home_opta_rating": [88.1],
            "away_opta_rank": [42],
            "opta_rating_diff": [2.5],
            "market_no_vig_prob_over": [0.51],
            "latest_snapshot_minutes_before_kickoff": [120.0],
        }
    )

    numeric, categorical = build_leakage_safe_feature_columns(frame)

    assert numeric == [
        "latest_snapshot_minutes_before_kickoff",
        "market_no_vig_prob_over",
    ]
    assert categorical == []
