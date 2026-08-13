from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ullebets_v2.matchups.form_profiles import (
    MATCHUP_FORM_METHOD,
    build_matchup_form_profiles,
)


def _profile(team_key: str, values: list[float]) -> dict:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    history = [
        {
            "matchId": f"{team_key}-{index}",
            "date": (start + timedelta(days=index)).date().isoformat(),
            "timestamp": (start + timedelta(days=index)).timestamp(),
            "val": value,
            "oppVal": value + 100.0,
        }
        for index, value in enumerate(values)
    ]
    return {
        "team_key": team_key,
        "league_key": "test-league",
        "match_type": "home",
        "statistics": {
            "for": {"totalShots": {"ALL": {"value": -1.0, "history": history}}},
            "against": {"totalShots": {"ALL": {"value": -1.0, "history": history}}},
            "leagueAverage": {"for": {}, "against": {}},
        },
    }


def test_matchup_form_uses_only_recent_twelve_and_weights_newer_matches() -> None:
    source_profiles = [
        _profile("team-a", [float(value) for value in range(1, 14)]),
        _profile("team-b", [1.0] * 13),
    ]

    profiles = build_matchup_form_profiles(source_profiles)
    team_a = next(row for row in profiles if row["team_key"] == "team-a")
    for_node = team_a["statistics"]["for"]["totalShots"]["ALL"]
    against_node = team_a["statistics"]["against"]["totalShots"]["ALL"]

    weights = [0.5 ** (age_days / 45.0) for age_days in range(11, -1, -1)]
    expected_for = sum(value * weight for value, weight in zip(range(2, 14), weights, strict=True)) / sum(weights)
    expected_against = sum((value + 100.0) * weight for value, weight in zip(range(2, 14), weights, strict=True)) / sum(weights)

    assert for_node["value"] == pytest.approx(expected_for)
    assert against_node["value"] == pytest.approx(expected_against)
    assert for_node["form"]["method"] == MATCHUP_FORM_METHOD
    assert for_node["form"]["sampleSize"] == 12
    assert for_node["rank"] == 1
    assert source_profiles[0]["statistics"]["for"]["totalShots"]["ALL"]["value"] == -1.0

