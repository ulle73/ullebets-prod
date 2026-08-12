from __future__ import annotations

from ullebets_v2.forward_exposures import (
    canonicalize_forward_bet_docs,
    forward_exposure_key,
    forward_selection_family,
)


def _legacy_row(
    prediction_key: str,
    *,
    prediction_type: str = "single",
    saved_at: str = "2026-07-28T09:00:00Z",
) -> dict:
    return {
        "prediction_key": prediction_key,
        "selection_key": "legacy-selection",
        "prediction_type": prediction_type,
        "export_mode": "combos" if prediction_type == "combo" else "daily",
        "match_key": "match-1",
        "stat_key": "cornerKicks",
        "scope": "away",
        "period": "ALL",
        "direction": "over",
        "line_value": 4.5,
        "saved_odds": 1.91,
        "saved_at": saved_at,
        "match_start_time": "2026-07-28T12:00:00Z",
        "invalid_for_model": False,
    }


def _v6_row() -> dict:
    return {
        "prediction_key": "v6-prediction",
        "selection_key": "v6-prediction",
        "prediction_type": "ev_registered_score_policy",
        "model_id": "ev_scope_interaction_recency45_asof_capped_v6",
        "model_status": "forward_test_only",
        "selection_policy_id": "v6_corners_away_total_forward_v1",
        "selection_policy_registry_id": "forward_policy_registry_v1",
        "match_key": "match-1",
        "stat_key": "cornerKicks",
        "scope": "away",
        "period": "ALL",
        "direction": "over",
        "line_value": 4.5,
        "selected_odds": 1.95,
        "odds_snapshot_time": "2026-07-28T10:00:00Z",
        "prediction_created_at": "2026-07-28T10:01:00Z",
        "match_start_time": "2026-07-28T12:00:00Z",
        "valid_for_forward_evaluation": True,
        "invalid_for_model": False,
    }


def test_canonical_forward_exposures_exclude_combo_legs_and_collapse_legacy_replays() -> None:
    rows = [
        _legacy_row("legacy-later", saved_at="2026-07-28T10:00:00Z"),
        _legacy_row("legacy-first"),
        _legacy_row("combo-leg", prediction_type="combo"),
        _v6_row(),
    ]

    canonical, audit = canonicalize_forward_bet_docs(rows)

    assert {row["prediction_key"] for row in canonical} == {
        "legacy-first",
        "v6-prediction",
    }
    assert audit == {
        "raw_count": 4,
        "canonical_count": 2,
        "excluded_combo_leg_count": 1,
        "excluded_shadow_prediction_count": 0,
        "collapsed_duplicate_count": 1,
    }
    assert {forward_selection_family(row) for row in canonical} == {"legacy", "v6"}
    assert forward_exposure_key(canonical[0]) != forward_exposure_key(canonical[1])


def test_v6_family_requires_frozen_v6_model_or_policy_provenance() -> None:
    assert forward_selection_family(_v6_row()) == "v6"
    assert forward_selection_family(_legacy_row("legacy")) == "legacy"
    assert forward_selection_family(
        _legacy_row("misleading") | {"headline": "V6 is mentioned in display text"}
    ) == "legacy"
