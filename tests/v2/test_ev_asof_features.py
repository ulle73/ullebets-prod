from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.asof_features import (
    build_asof_compact_model_features,
    build_asof_context_model_features,
)


def test_asof_features_exclude_matches_unavailable_at_snapshot() -> None:
    target = pd.DataFrame(
        [
            {
                "sample_key": "target|cornerKicks|ALL|home",
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "home",
                "line_value": 5.5,
                "over_odds": 1.9,
                "under_odds": 1.9,
                "league_name_normalized": "Premier League",
                "odds_snapshot_time": "2026-01-08T12:00:00Z",
                "kickoff_ts": pd.Timestamp(
                    "2026-01-10T14:00:00Z"
                ).timestamp(),
                "latest_snapshot_minutes_before_kickoff": 3000.0,
            }
        ]
    )
    rows = []
    for (
        match_id,
        kickoff,
        team,
        role,
        team_value,
        opponent_value,
    ) in [
        (
            "old-home",
            "2026-01-01T14:00:00Z",
            "Arsenal",
            "home",
            6.0,
            3.0,
        ),
        (
            "old-away",
            "2026-01-02T14:00:00Z",
            "Chelsea",
            "away",
            2.0,
            5.0,
        ),
        (
            "not-finished-at-snapshot",
            "2026-01-08T11:00:00Z",
            "Arsenal",
            "home",
            99.0,
            0.0,
        ),
        (
            "current",
            "2026-01-10T14:00:00Z",
            "Arsenal",
            "home",
            99.0,
            0.0,
        ),
    ]:
        rows.append(
            {
                "match_id": match_id,
                "kickoff_ts": pd.Timestamp(kickoff).timestamp(),
                "team_name": team,
                "team_role": role,
                "period": "ALL",
                "stat_item_key": "cornerKicks",
                "team_value": team_value,
                "opponent_value": opponent_value,
            }
        )

    features, audit = build_asof_compact_model_features(
        target,
        pd.DataFrame(rows),
        availability_buffer_hours=3.0,
    )

    assert features.iloc[0]["history_role_attack_3"] == pytest.approx(6.0)
    assert features.iloc[0]["history_role_defense_3"] == pytest.approx(5.0)
    assert features.iloc[0]["history_role_expected_3"] == pytest.approx(5.5)
    assert features.iloc[0]["baseline_lambda"] == pytest.approx(5.5)
    assert audit["history_observations_excluded_by_snapshot"] >= 1
    assert audit["history_observations_at_or_after_snapshot_used"] == 0


def test_asof_context_excludes_unavailable_cross_stat_history() -> None:
    target = pd.DataFrame(
        [
            {
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "odds_snapshot_time": "2026-01-08T12:00:00Z",
                "kickoff_ts": pd.Timestamp(
                    "2026-01-10T14:00:00Z"
                ).timestamp(),
            }
        ]
    )
    stats = pd.DataFrame(
        [
            {
                "match_id": "old",
                "kickoff_ts": pd.Timestamp(
                    "2026-01-01T14:00:00Z"
                ).timestamp(),
                "team_name": "Arsenal",
                "team_role": "home",
                "period": "ALL",
                "stat_item_key": "expectedGoals",
                "team_value": 2.1,
                "opponent_value": 0.8,
            },
            {
                "match_id": "unavailable",
                "kickoff_ts": pd.Timestamp(
                    "2026-01-08T11:00:00Z"
                ).timestamp(),
                "team_name": "Arsenal",
                "team_role": "home",
                "period": "ALL",
                "stat_item_key": "expectedGoals",
                "team_value": 99.0,
                "opponent_value": 99.0,
            },
        ]
    )

    features, audit = build_asof_context_model_features(
        target,
        stats,
        availability_buffer_hours=3.0,
    )

    assert features.iloc[0][
        "context_expectedGoals_role_home_for_5"
    ] == pytest.approx(2.1)
    assert features.iloc[0][
        "context_expectedGoals_role_home_against_5"
    ] == pytest.approx(0.8)
    assert audit[
        "history_observations_excluded_by_snapshot"
    ] >= 1
    assert audit[
        "history_observations_at_or_after_snapshot_used"
    ] == 0
