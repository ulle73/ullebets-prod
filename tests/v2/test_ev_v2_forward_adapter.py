from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.v2_forward_adapter import (
    build_v2_forward_model_frame,
    select_canonical_prematch_markets,
)


def test_forward_adapter_handles_empty_snapshot_window() -> None:
    frame, audit = build_v2_forward_model_frame(
        snapshots=pd.DataFrame(),
        fixtures=pd.DataFrame(),
        match_stats=pd.DataFrame(),
    )

    assert frame.empty
    assert audit["canonical_markets"] == 0
    assert audit["history_observations_at_or_after_snapshot_used"] == 0


def test_canonical_market_uses_latest_prematch_snapshot_and_balanced_line() -> None:
    snapshots = pd.DataFrame(
        [
            {
                "snapshot_key": "old",
                "offer_key": "balanced",
                "match_key": "m1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line": 9.5,
                "over_odds": 1.91,
                "under_odds": 1.91,
                "snapshot_time": "2026-07-29T10:00:00Z",
                "match_start_time": "2026-07-29T14:00:00Z",
                "invalid_for_model": False,
            },
            {
                "snapshot_key": "latest",
                "offer_key": "balanced",
                "match_key": "m1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line": 9.5,
                "over_odds": 1.95,
                "under_odds": 1.85,
                "snapshot_time": "2026-07-29T13:00:00Z",
                "match_start_time": "2026-07-29T14:00:00Z",
                "invalid_for_model": False,
            },
            {
                "snapshot_key": "unbalanced",
                "offer_key": "unbalanced",
                "match_key": "m1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line": 10.5,
                "over_odds": 1.45,
                "under_odds": 2.6,
                "snapshot_time": "2026-07-29T13:00:00Z",
                "match_start_time": "2026-07-29T14:00:00Z",
                "invalid_for_model": False,
            },
            {
                "snapshot_key": "post-start",
                "offer_key": "balanced",
                "match_key": "m1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line": 9.5,
                "over_odds": 2.1,
                "under_odds": 1.7,
                "snapshot_time": "2026-07-29T14:01:00Z",
                "match_start_time": "2026-07-29T14:00:00Z",
                "invalid_for_model": True,
            },
        ]
    )

    canonical = select_canonical_prematch_markets(snapshots)

    assert canonical["snapshot_key"].tolist() == ["latest"]
    assert canonical.iloc[0]["line"] == 9.5


def test_forward_features_use_only_prior_canonical_match_stats() -> None:
    fixtures = pd.DataFrame(
        [
            {
                "match_key": "past-home",
                "start_time": "2026-07-01T14:00:00Z",
                "home_team_key": "arsenal",
                "away_team_key": "other-a",
                "home_team_name": "Arsenal",
                "away_team_name": "Other A",
                "league_name": "Premier League",
            },
            {
                "match_key": "past-away",
                "start_time": "2026-07-02T14:00:00Z",
                "home_team_key": "other-b",
                "away_team_key": "chelsea",
                "home_team_name": "Other B",
                "away_team_name": "Chelsea",
                "league_name": "Premier League",
            },
            {
                "match_key": "not-finished-at-snapshot",
                "start_time": "2026-07-10T10:00:00Z",
                "home_team_key": "arsenal",
                "away_team_key": "other-d",
                "home_team_name": "Arsenal",
                "away_team_name": "Other D",
                "league_name": "Premier League",
            },
            {
                "match_key": "after-snapshot",
                "start_time": "2026-07-10T13:00:00Z",
                "home_team_key": "other-e",
                "away_team_key": "chelsea",
                "home_team_name": "Other E",
                "away_team_name": "Chelsea",
                "league_name": "Premier League",
            },
            {
                "match_key": "current",
                "start_time": "2026-07-10T14:00:00Z",
                "home_team_key": "arsenal",
                "away_team_key": "chelsea",
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "league_name": "Premier League",
            },
            {
                "match_key": "future",
                "start_time": "2026-07-20T14:00:00Z",
                "home_team_key": "arsenal",
                "away_team_key": "other-c",
                "home_team_name": "Arsenal",
                "away_team_name": "Other C",
                "league_name": "Premier League",
            },
        ]
    )
    stats = pd.DataFrame(
        [
            {
                "match_key": match_key,
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": scope,
                "actual_value": value,
            }
            for match_key, home, away in [
                ("past-home", 6.0, 3.0),
                ("past-away", 5.0, 2.0),
                ("not-finished-at-snapshot", 99.0, 99.0),
                ("after-snapshot", 99.0, 99.0),
                ("current", 99.0, 99.0),
                ("future", 99.0, 0.0),
            ]
            for scope, value in [
                ("home", home),
                ("away", away),
                ("total", home + away),
            ]
        ]
    )
    snapshots = pd.DataFrame(
        [
            {
                "snapshot_key": "current-line",
                "offer_key": "current-line",
                "match_key": "current",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "home",
                "line": 5.5,
                "over_odds": 1.9,
                "under_odds": 1.9,
                "snapshot_time": "2026-07-10T12:00:00Z",
                "match_start_time": "2026-07-10T14:00:00Z",
                "invalid_for_model": False,
            }
        ]
    )

    frame, audit = build_v2_forward_model_frame(
        snapshots=snapshots,
        fixtures=fixtures,
        match_stats=stats,
    )

    assert len(frame) == 1
    assert frame.iloc[0]["history_role_attack_3"] == pytest.approx(6.0)
    assert frame.iloc[0]["history_role_defense_3"] == pytest.approx(5.0)
    assert frame.iloc[0]["history_role_expected_3"] == pytest.approx(5.5)
    assert frame.iloc[0]["baseline_lambda"] == pytest.approx(5.5)
    assert frame.iloc[0]["match_key"] == "current"
    assert frame.iloc[0]["snapshot_key"] == "current-line"
    assert frame.iloc[0]["offer_key"] == "current-line"
    assert audit["history_observations_at_or_after_snapshot_used"] == 0
    assert audit["history_observations_excluded_by_snapshot"] == 2
