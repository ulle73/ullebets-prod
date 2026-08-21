from datetime import UTC, datetime, timedelta

import pytest

from ullebets_v2.market_bias.domain import (
    MARKET_BIAS_METHOD_VERSION,
    build_bias_profile,
    build_observation_docs,
    build_profile_key,
    select_main_line,
)


def _at(minutes: int) -> datetime:
    return datetime(2026, 8, 21, 18, 0, tzinfo=UTC) + timedelta(minutes=minutes)


def _snapshot(**overrides: object) -> dict[str, object]:
    return {
        "snapshot_key": "snapshot-1",
        "snapshot_label": "T_MINUS_60M",
        "snapshot_time": _at(0),
        "invalid_for_model": False,
        "line_value": 10.5,
        "over_odds": 2.02,
        "under_odds": None,
        "offer_key": "offer-1",
        **overrides,
    }


def test_select_main_line_uses_latest_valid_prematch_batch_and_deterministic_ties() -> None:
    kickoff = _at(90)
    selected = select_main_line(
        snapshots=[
            _snapshot(snapshot_key="old", line_value=9.5, over_odds=1.99),
            _snapshot(snapshot_key="post-start", snapshot_time=kickoff, line_value=8.5, over_odds=2.0),
            _snapshot(snapshot_key="invalid", snapshot_time=_at(60), invalid_for_model=True, over_odds=2.0),
            _snapshot(snapshot_key="later-b", snapshot_time=_at(60), snapshot_label="T_MINUS_30M", line_value=11.5, over_odds=1.98, offer_key="b"),
            _snapshot(snapshot_key="later-a", snapshot_time=_at(60), snapshot_label="T_MINUS_30M", line_value=10.5, over_odds=1.98, offer_key="a"),
        ],
        match_start_time=kickoff,
    )

    assert selected is not None
    assert selected["snapshot_label"] == "T_MINUS_30M"
    assert selected["over_odds"] == 1.98
    assert selected["line_value"] == 10.5
    assert selected["offer_key"] == "a"


def test_select_main_line_supports_corners_both_sides_and_rejects_unqualified_prices() -> None:
    kickoff = _at(90)
    selected = select_main_line(
        snapshots=[_snapshot(over_odds=2.04, under_odds=1.84)],
        match_start_time=kickoff,
    )
    assert selected is not None
    assert selected["under_odds"] == 1.84

    assert select_main_line(
        snapshots=[_snapshot(over_odds=1.69), _snapshot(snapshot_key="high", over_odds=2.31)],
        match_start_time=kickoff,
    ) is None


def test_select_main_line_supports_shots_with_only_an_over_price() -> None:
    selected = select_main_line(
        snapshots=[_snapshot(stat_key="totalShots", over_odds=1.98, under_odds=None)],
        match_start_time=_at(90),
    )

    assert selected is not None
    assert selected["stat_key"] == "totalShots"
    assert selected["over_odds"] == 1.98
    assert selected["under_odds"] is None


@pytest.mark.parametrize(
    ("market_scope", "actual_value", "expected_result", "expected_teams"),
    [
        ("home", 11.0, "over", ["home-team"]),
        ("away", 10.0, "under", ["away-team"]),
        ("total", 10.5, "push", ["home-team", "away-team"]),
    ],
)
def test_build_observation_docs_preserves_exact_outcome_and_context_ownership(
    market_scope: str,
    actual_value: float,
    expected_result: str,
    expected_teams: list[str],
) -> None:
    selected = _snapshot(market_scope=market_scope, stat_key="cornerKicks", period="ALL")
    docs = build_observation_docs(
        selected=selected,
        actual_value=actual_value,
        fixture={
            "match_key": "match-1",
            "source_match_id": "source-1",
            "league_key": "league-1",
            "home_team_key": "home-team",
            "away_team_key": "away-team",
            "match_start_time": _at(90),
        },
        outcome_available_at=_at(180),
        source_kind="v2_forward",
        source_record_key="canonical:match-1",
        source_payload_hash="payload-hash",
        run_id="run-1",
    )

    assert [doc["team_key"] for doc in docs] == expected_teams
    assert {doc["line_result"] for doc in docs} == {expected_result}
    assert {doc["residual_value"] for doc in docs} == {actual_value - 10.5}
    assert all(doc["method_version"] == MARKET_BIAS_METHOD_VERSION for doc in docs)
    assert all(doc["run_id"] == "run-1" for doc in docs)


def _observation(index: int, *, result: str = "over", residual: float = 1.0, available_at: datetime | None = None) -> dict[str, object]:
    observed_at = _at(-index * 24 * 60)
    return {
        "observation_key": f"observation-{index}",
        "team_key": "team-1",
        "league_key": "league-1",
        "venue_context": "home",
        "market_scope": "home",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "line_result": result,
        "residual_value": residual,
        "snapshot_time": observed_at,
        "outcome_available_at": available_at or observed_at + timedelta(hours=3),
        "match_start_time": observed_at + timedelta(hours=2),
        "snapshot_label": "T_MINUS_30M",
    }


def test_build_bias_profile_uses_rolling_weighted_leakage_safe_contract() -> None:
    cutoff = _at(60)
    observations = [_observation(index) for index in range(14)]
    observations.extend(
        [
            _observation(20, result="push", residual=0.0),
            _observation(21, available_at=cutoff),
        ]
    )
    profile = build_bias_profile(
        observations,
        as_of=cutoff,
        profile_date="2026-08-21",
        run_id="run-1",
    )

    assert profile["sample_size"] == 12
    assert profile["non_push_sample_size"] == 12
    assert profile["push_count"] == 0
    assert profile["raw_over_rate"] == 1.0
    assert profile["posterior_over_rate"] < 1.0
    assert profile["weighted_mean_residual"] == pytest.approx(1.0)
    assert 0.0 < profile["shrunk_mean_residual"] < 1.0
    assert 4.0 <= profile["effective_sample_size"] <= 12.0
    assert profile["method_version"] == MARKET_BIAS_METHOD_VERSION
    assert profile["as_of"] == cutoff
    assert profile["profile_date"] == "2026-08-21"
    assert profile["run_id"] == "run-1"


def test_build_bias_profile_gates_small_samples_and_marks_conflicting_signs_neutral() -> None:
    cutoff = _at(60)
    insufficient = build_bias_profile(
        [_observation(index) for index in range(5)],
        as_of=cutoff,
        profile_date="2026-08-21",
        run_id="run-1",
    )
    assert insufficient["direction"] == "insufficient"
    assert insufficient["strength"] == "none"

    neutral = build_bias_profile(
        [_observation(index, result="over", residual=-1.0) for index in range(8)],
        as_of=cutoff,
        profile_date="2026-08-21",
        run_id="run-1",
    )
    assert neutral["direction"] == "neutral"


def test_build_bias_profile_counts_selected_window_push_with_zero_residual() -> None:
    cutoff = _at(60)
    observations = [_observation(index) for index in range(1, 12)]
    observations.append(_observation(12, result="push", residual=0.0))

    profile = build_bias_profile(
        observations,
        as_of=cutoff,
        profile_date="2026-08-21",
        run_id="run-1",
    )

    assert profile["sample_size"] == 12
    assert profile["non_push_sample_size"] == 11
    assert profile["push_count"] == 1
    assert profile["weighted_mean_residual"] < 1.0


def test_build_bias_profile_rejects_outcome_available_exactly_at_cutoff() -> None:
    cutoff = _at(60)
    observations = [_observation(index) for index in range(1, 7)]
    observations.append(_observation(7, available_at=cutoff))

    profile = build_bias_profile(
        observations,
        as_of=cutoff,
        profile_date="2026-08-21",
        run_id="run-1",
    )

    assert profile["sample_size"] == 6
    assert "observation-7" not in profile["observation_keys"]


def test_build_bias_profile_rejects_mixed_context_even_outside_rolling_window() -> None:
    cutoff = _at(60)
    observations = [_observation(index) for index in range(1, 14)]
    observations.append({**_observation(14), "team_key": "other-team"})

    with pytest.raises(ValueError, match="exact market-bias context"):
        build_bias_profile(
            observations,
            as_of=cutoff,
            profile_date="2026-08-21",
            run_id="run-1",
        )


def test_build_profile_key_includes_every_context_identity_component() -> None:
    key = build_profile_key(
        profile_date="2026-08-21",
        team_key="team-1",
        league_key="league-1",
        venue_context="home",
        market_scope="total",
        stat_key="cornerKicks",
        period="ALL",
        method_version=MARKET_BIAS_METHOD_VERSION,
    )
    assert "team-1" in key
    assert "league-1" in key
    assert MARKET_BIAS_METHOD_VERSION in key
