from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ullebets_v2.ev_model.score_evaluation import (
    build_registered_policy_evaluation,
    build_score_policy_evaluation,
    fingerprint_policy_registry,
)


def _score(
    *,
    model_id: str,
    direction: str,
    probability: float,
    odds: float,
    snapshot_key: str = "snap-1",
    created_hour: int = 11,
    stat_key: str = "cornerKicks",
    scope: str = "total",
) -> dict:
    return {
        "score_key": (
            f"{model_id}|{snapshot_key}|{stat_key}|{scope}|"
            f"{direction}"
        ),
        "model_id": model_id,
        "match_key": "match-1",
        "sample_key": (
            f"match-1|{stat_key}|ALL|{scope}"
        ),
        "side_key": (
            f"match-1|{stat_key}|ALL|{scope}|{direction}"
        ),
        "snapshot_key": snapshot_key,
        "offer_key": (
            f"match-1|{stat_key}|{scope}|ALL|10.5"
        ),
        "stat_key": stat_key,
        "period": "ALL",
        "scope": scope,
        "line_value": 10.5,
        "direction": direction,
        "offered_odds": odds,
        "predicted_win_probability": probability,
        "expected_roi_units": probability * odds - 1.0,
        "odds_snapshot_time": datetime(
            2026, 7, 30, 10, tzinfo=UTC
        ),
        "score_created_at": datetime(
            2026, 7, 30, created_hour, tzinfo=UTC
        ),
        "match_start_time": datetime(
            2026, 7, 30, 14, tzinfo=UTC
        ),
        "valid_for_policy_evaluation": True,
        "invalid_for_model": False,
    }


def test_score_policy_evaluation_settles_selected_sides_without_mutation() -> None:
    scores = [
        _score(
            model_id="v3",
            direction="over",
            probability=0.60,
            odds=2.0,
        ),
        _score(
            model_id="v3",
            direction="under",
            probability=0.40,
            odds=2.0,
        ),
        _score(
            model_id="v4",
            direction="over",
            probability=0.45,
            odds=2.0,
        ),
        _score(
            model_id="v4",
            direction="under",
            probability=0.55,
            odds=2.0,
        ),
    ]

    report = build_score_policy_evaluation(
        scores=scores,
        match_stats=[
            {
                "match_key": "match-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "all",
                "actual_value": 12,
            }
        ],
        match_results=[
            {
                "match_key": "match-1",
                "home_score": 2,
                "away_score": 1,
            }
        ],
        model_ids=["v3", "v4"],
        minimum_ev=0.075,
        maximum_ev=0.25,
        bootstrap_iterations=100,
    )

    by_model = {
        row["model_id"]: row
        for row in report["models"]
    }
    assert by_model["v3"]["selected_bets"] == 1
    assert by_model["v3"]["settlement"]["win"] == 1
    assert by_model["v3"]["performance"]["roi_pct"] == 100.0
    assert by_model["v4"]["selected_bets"] == 1
    assert by_model["v4"]["settlement"]["loss"] == 1
    assert by_model["v4"]["performance"]["roi_pct"] == -100.0
    assert report["common_scored_markets"] == 1
    assert all("actual_value" not in row for row in scores)


def test_score_policy_freezes_first_eligible_batch_per_match() -> None:
    early_over = _score(
        model_id="v3",
        direction="over",
        probability=0.55,
        odds=2.0,
    )
    later_under = _score(
        model_id="v3",
        direction="under",
        probability=0.60,
        odds=2.0,
        snapshot_key="snap-2",
        created_hour=12,
    )

    report = build_score_policy_evaluation(
        scores=[early_over, later_under],
        match_stats=[
            {
                "match_key": "match-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "all",
                "actual_value": 12,
            }
        ],
        match_results=[
            {
                "match_key": "match-1",
                "home_score": 1,
                "away_score": 0,
            }
        ],
        model_ids=["v3"],
        minimum_ev=0.075,
        maximum_ev=0.25,
        bootstrap_iterations=100,
    )

    model = report["models"][0]
    assert model["selected_bets"] == 1
    assert model["settlement"]["win"] == 1
    assert model["performance"]["roi_pct"] == 100.0


def test_registered_policy_filters_are_frozen_before_settlement() -> None:
    scores = [
        _score(
            model_id="v4",
            direction="over",
            probability=0.60,
            odds=2.0,
            stat_key="cornerKicks",
            scope="away",
        ),
        _score(
            model_id="v4",
            direction="over",
            probability=0.61,
            odds=2.0,
            stat_key="cornerKicks",
            scope="home",
        ),
        _score(
            model_id="v4",
            direction="over",
            probability=0.59,
            odds=2.0,
            stat_key="cornerKicks",
            scope="total",
        ),
        _score(
            model_id="v4",
            direction="over",
            probability=0.62,
            odds=2.0,
            stat_key="shotsOnGoal",
            scope="home",
        ),
    ]
    policies = [
        {
            "policy_id": "v4-corners-away-total",
            "model_id": "v4",
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "maximum_bets_per_match": 1,
            "filters": {
                "stat_keys": ["cornerKicks"],
                "scopes": ["away", "total"],
            },
        },
        {
            "policy_id": "v4-shots",
            "model_id": "v4",
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "filters": {
                "stat_keys": ["shotsOnGoal"],
            },
        },
    ]

    report = build_registered_policy_evaluation(
        scores=scores,
        match_stats=[],
        match_results=[],
        policies=policies,
        bootstrap_iterations=100,
    )
    by_policy = {
        row["policy_id"]: row
        for row in report["policies"]
    }

    assert (
        by_policy["v4-corners-away-total"]["selected_bets"]
        == 1
    )
    assert (
        by_policy["v4-corners-away-total"][
            "maximum_bets_per_match"
        ]
        == 1
    )
    assert by_policy["v4-shots"]["selected_bets"] == 1
    assert all(
        row["settlement"]["pending"] == 1
        for row in by_policy.values()
    )
    assert report["policy_registry_fingerprint"]


def test_registry_fingerprint_covers_promotion_gate() -> None:
    registry = {
        "registry_id": "v1",
        "promotion_gate": {"minimum_settled_bets": 300},
        "policies": [{"policy_id": "primary"}],
    }
    changed = {
        **registry,
        "promotion_gate": {"minimum_settled_bets": 500},
    }

    assert fingerprint_policy_registry(
        registry
    ) != fingerprint_policy_registry(changed)
    assert fingerprint_policy_registry(registry) == (
        fingerprint_policy_registry(
            {
                "policies": [{"policy_id": "primary"}],
                "promotion_gate": {
                    "minimum_settled_bets": 300
                },
                "registry_id": "v1",
            }
        )
    )


def test_registered_policy_reports_clv_and_promotion_gate() -> None:
    policy = {
        "policy_id": "primary",
        "model_id": "v3",
        "minimum_ev": 0.075,
        "maximum_ev": 0.25,
        "filters": {"stat_keys": ["cornerKicks"]},
    }
    gate = {
        "minimum_settled_bets": 300,
        "minimum_match_clusters": 150,
        "minimum_clv_coverage_pct": 80,
        "require_positive_clustered_95pct_lower_bound": True,
        "require_positive_mean_clv": True,
        "require_multiple_comparison_adjusted_p_below": 0.05,
        "require_zero_timing_outcome_duplicate_feature_audit_errors": True,
    }

    report = build_registered_policy_evaluation(
        scores=[
            _score(
                model_id="v3",
                direction="over",
                probability=0.60,
                odds=2.0,
            )
        ],
        match_stats=[],
        match_results=[],
        closing_lines=[
            {
                "offer_key": (
                    "match-1|cornerKicks|total|ALL|10.5"
                ),
                "closing_snapshot_time": datetime(
                    2026, 7, 30, 13, 50, tzinfo=UTC
                ),
                "match_start_time": datetime(
                    2026, 7, 30, 14, tzinfo=UTC
                ),
                "closing_over_odds": 1.80,
                "closing_under_odds": 2.00,
            }
        ],
        policies=[policy],
        promotion_gate=gate,
        multiple_comparison_family_size=10,
        bootstrap_iterations=100,
    )
    row = report["policies"][0]

    assert row["clv"]["coverage_pct"] == 100.0
    assert row["clv"]["mean_clv_pct"] == pytest.approx(
        11.1111111111
    )
    assert (
        row["promotion_gate"]["eligible_for_promotion"]
        is False
    )
    assert row["promotion_gate"]["status"] == (
        "insufficient_evidence"
    )


def test_registered_policy_excludes_out_of_domain_scores() -> None:
    score = _score(
        model_id="v3",
        direction="over",
        probability=0.60,
        odds=2.0,
    )
    score["feature_values"] = {
        "league_name_normalized": "Brasileirão Série A",
        "period": "ALL",
        "scope": "total",
        "stat_key": "cornerKicks",
    }

    report = build_registered_policy_evaluation(
        scores=[score],
        match_stats=[],
        match_results=[],
        policies=[
            {
                "policy_id": "primary",
                "model_id": "v3",
                "minimum_ev": 0.075,
                "maximum_ev": 0.25,
                "filters": {"stat_keys": ["cornerKicks"]},
            }
        ],
        training_domain_by_model={
            "v3": {
                "league_name_normalized": ("Serie A",),
                "period": ("ALL",),
                "scope": ("total",),
                "stat_key": ("cornerKicks",),
            }
        },
        bootstrap_iterations=100,
    )
    row = report["policies"][0]

    assert row["scores"] == 1
    assert row["in_domain_scores"] == 0
    assert row["selected_bets"] == 0
    assert row["domain"]["status"] == (
        "out_of_domain_scores_excluded"
    )
    assert row["domain"]["unknown_category_counts"] == {
        "league_name_normalized": {
            "Brasileirão Série A": 1
        }
    }
