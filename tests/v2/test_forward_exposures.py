from __future__ import annotations

from ullebets_v2.forward_exposures import (
    canonicalize_forward_bet_docs,
    forward_exposure_key,
    forward_selection_family,
    group_forward_observation_docs,
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


def test_checkpoint_observations_are_distinct_but_share_display_group() -> None:
    first = _v6_row() | {
        "prediction_key": "journal|score-t3d",
        "selection_key": "journal|score-t3d",
        "selection_policy_id": "v6_full_domain_checkpoint_journal_v2",
        "selection_policy_registry_id": "forward_policy_registry_v2",
        "selection_granularity": "checkpoint_observation",
        "snapshot_key": "snapshot-t3d",
        "snapshot_label": "T_MINUS_3D",
        "expected_roi_units": 0.08,
    }
    later = first | {
        "prediction_key": "journal|score-t2h",
        "selection_key": "journal|score-t2h",
        "snapshot_key": "snapshot-t2h",
        "snapshot_label": "T_MINUS_2H",
        "odds_snapshot_time": "2026-07-28T10:30:00Z",
        "prediction_created_at": "2026-07-28T10:31:00Z",
        "expected_roi_units": 0.12,
    }

    canonical, audit = canonicalize_forward_bet_docs([first, later])

    assert {row["prediction_key"] for row in canonical} == {
        "journal|score-t3d",
        "journal|score-t2h",
    }
    assert len(
        {row["canonical_exposure_key"] for row in canonical}
    ) == 1
    assert audit["canonical_count"] == 2
    assert audit["collapsed_duplicate_count"] == 0


def test_display_group_uses_best_ev_and_aggregates_every_one_unit_observation() -> None:
    first = _v6_row() | {
        "prediction_key": "journal|score-t3d",
        "selection_key": "journal|score-t3d",
        "selection_policy_id": "v6_full_domain_checkpoint_journal_v2",
        "selection_granularity": "checkpoint_observation",
        "snapshot_label": "T_MINUS_3D",
        "expected_roi_units": 0.08,
        "stake_units": 1.0,
        "pnl_units": 0.95,
        "official_clv": True,
        "beat_closing_line": True,
        "clv_pct": 4.0,
        "settlement_status": "settled",
        "settlement_result": "win",
    }
    best = first | {
        "prediction_key": "journal|score-t2h",
        "selection_key": "journal|score-t2h",
        "snapshot_label": "T_MINUS_2H",
        "expected_roi_units": 0.12,
        "stake_units": 1.0,
        "pnl_units": 1.05,
        "official_clv": True,
        "beat_closing_line": False,
        "clv_pct": -2.0,
    }

    grouped = group_forward_observation_docs([first, best])

    assert len(grouped) == 1
    row = grouped[0]
    assert row["prediction_key"] == "journal|score-t2h"
    assert row["observation_count"] == 2
    assert row["observation_keys"] == [
        "journal|score-t3d",
        "journal|score-t2h",
    ]
    assert row["snapshot_labels"] == ["T_MINUS_3D", "T_MINUS_2H"]
    assert row["best_snapshot_label"] == "T_MINUS_2H"
    assert row["stake_units"] == 2.0
    assert row["pnl_units"] == 2.0
    assert row["roi_units"] == 1.0
    assert row["settled_observation_count"] == 2
    assert row["official_clv_count"] == 2
    assert row["beat_closing_line_count"] == 1
    assert row["clv_beat_rate"] == 0.5
    assert row["average_clv_pct"] == 1.0
