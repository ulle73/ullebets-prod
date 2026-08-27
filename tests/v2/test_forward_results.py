from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.forward_results.service import run_forward_result_refresh


def test_run_forward_result_refresh_dry_run_builds_settled_clv_tracked_rows() -> None:
    summary = run_forward_result_refresh(
        forward_bet_docs=[
            {
                "prediction_key": "pred-1",
                "selection_key": "sel-1",
                "tracking_key": "sel-1",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "league_name": "Premier League",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "saved_odds": 2.0,
                "saved_at": "2026-07-28T09:50:00Z",
                "match_start_time": "2026-07-28T10:00:00Z",
                "stake_units": 1,
                "snapshot_key": "snapshot-t2h",
                "snapshot_label": "T_MINUS_2H",
                "snapshot_type": "research",
                "selection_granularity": "checkpoint_observation",
                "expected_roi_units": 0.14,
            }
        ],
        clv_tracking_docs=[
            {
                "clv_key": "pred-1",
                "prediction_key": "pred-1",
                "tracking_key": "sel-1",
                "selection_key": "sel-1",
                "tracking_source": "forward_bets",
                "closing_key": "offer-1",
                "opening_snapshot_label": "CURRENT",
                "opening_snapshot_time": "2026-07-28T09:50:00Z",
                "opening_odds": 2.0,
                "latest_snapshot_label": "T_MINUS_10M",
                "latest_snapshot_time": "2026-07-28T09:55:00Z",
                "latest_observed_odds": 1.9,
                "closing_snapshot_label": "T_MINUS_10M",
                "closing_snapshot_time": "2026-07-28T09:55:00Z",
                "closing_quality": "t10",
                "closing_age_minutes": 5,
                "official_clv": True,
                "clv_basis": "T_MINUS_10M",
                "closing_odds": 1.8,
                "clv_pct": 11.1,
                "implied_edge_delta": 5.56,
                "beat_closing_line": True,
                "clv_status": "tracked",
                "prematch_observation_count": 2,
                "price_history": [{"snapshot_label": "CURRENT", "observed_at": "2026-07-28T09:50:00Z", "odds": 2.0}],
            }
        ],
        settled_bet_docs=[
            {
                "settlement_key": "pred-1",
                "prediction_key": "pred-1",
                "tracking_key": "sel-1",
                "selection_key": "sel-1",
                "selection_source": "forward_bet",
                "source_collection": "forward_bets",
                "settlement_status": "settled",
                "settlement_result": "win",
                "actual_value": 12,
                "home_value": 7,
                "away_value": 5,
                "win": True,
                "roi_units": 1.0,
                "pnl_units": 1.0,
                "stake_units": 1,
                "actual_source": "match-1:cornerKicks:ALL:all",
                "actual_source_status": "resolved",
                "settled_at": "2026-07-28T12:00:00Z",
            }
        ],
        dry_run=True,
        refreshed_at=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
    )

    assert summary["forward_results"] == 1
    assert summary["status_counts"] == {"settled": 1}
    assert summary["clv_status_counts"] == {"tracked": 1}
    assert summary["settlement_status_counts"] == {"settled": 1}
    assert summary["timing_status_counts"] == {"prematch_valid": 1}
    assert summary["beat_close_count"] == 1
    assert summary["avg_clv_pct"] == 11.1
    assert summary["pnl_units"] == 1.0
    assert summary["roi_pct_all_tracked"] == 100.0
    row = summary["result_docs"][0]
    assert row["result_loop_key"] == "pred-1"
    assert row["result_loop_status"] == "settled"
    assert row["closing_odds"] == 1.8
    assert row["closing_quality"] == "t10"
    assert row["closing_policy_version"] == "accepted_t30_t10_v2"
    assert row["accepted_clv"] is True
    assert row["eligible_for_promotion_clv"] is True
    assert row["official_clv"] is True
    assert row["settlement_result"] == "win"
    assert row["odds_captured_after_start"] is False
    assert row["snapshot_key"] == "snapshot-t2h"
    assert row["snapshot_label"] == "T_MINUS_2H"
    assert row["snapshot_type"] == "research"
    assert row["selection_granularity"] == "checkpoint_observation"
    assert row["expected_roi_units"] == 0.14


def test_forward_results_use_one_canonical_straight_exposure() -> None:
    shared = {
        "selection_key": "shared-selection",
        "tracking_key": "shared-selection",
        "match_key": "match-1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "direction": "over",
        "line_value": 10.5,
        "saved_odds": 2.0,
        "match_start_time": "2026-07-28T10:00:00Z",
    }
    summary = run_forward_result_refresh(
        forward_bet_docs=[
            shared | {"prediction_key": "first", "prediction_type": "single", "saved_at": "2026-07-28T09:00:00Z"},
            shared | {"prediction_key": "replay", "prediction_type": "single", "saved_at": "2026-07-28T09:05:00Z"},
            shared | {"prediction_key": "combo-leg", "prediction_type": "combo", "export_mode": "combos", "saved_at": "2026-07-28T09:00:00Z"},
        ],
        clv_tracking_docs=[],
        settled_bet_docs=[],
        dry_run=True,
        refreshed_at=datetime(2026, 7, 28, 9, 30, tzinfo=UTC),
    )

    assert summary["forward_results"] == 1
    assert summary["result_docs"][0]["prediction_key"] == "first"
    assert summary["forward_exposure_audit"]["excluded_combo_leg_count"] == 1
    assert summary["forward_exposure_audit"]["collapsed_duplicate_count"] == 1


def test_forward_results_report_t30_fallback_separately() -> None:
    summary = run_forward_result_refresh(
        forward_bet_docs=[
            {
                "prediction_key": "pred-1",
                "selection_key": "sel-1",
                "tracking_key": "sel-1",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "saved_odds": 2.0,
                "saved_at": "2026-07-28T09:00:00Z",
                "match_start_time": "2026-07-28T10:00:00Z",
            }
        ],
        clv_tracking_docs=[
            {
                "clv_key": "pred-1",
                "prediction_key": "pred-1",
                "tracking_key": "sel-1",
                "selection_key": "sel-1",
                "closing_key": "offer-1",
                "closing_snapshot_label": "T_MINUS_30M",
                "closing_snapshot_time": "2026-07-28T09:30:00Z",
                "closing_quality": "t30_fallback",
                "closing_policy_version": "accepted_t30_t10_v2",
                "accepted_clv": True,
                "eligible_for_promotion_clv": False,
                "closing_age_minutes": 30,
                "official_clv": False,
                "clv_basis": "T_MINUS_30M",
                "closing_odds": 1.8,
                "clv_pct": 11.1,
                "beat_closing_line": True,
                "clv_status": "tracked_fallback_t30",
            }
        ],
        settled_bet_docs=[],
        dry_run=True,
        refreshed_at=datetime(2026, 7, 28, 9, 31, tzinfo=UTC),
    )

    assert summary["fallback_t30_clv_count"] == 1
    assert summary["accepted_clv_count"] == 1
    assert summary["t30_clv_count"] == 1
    assert summary["t10_clv_count"] == 0
    assert summary["average_accepted_clv_pct"] == 11.1
    assert summary["accepted_beat_closing_line_count"] == 1
    assert summary["avg_fallback_t30_clv_pct"] == 11.1
    assert summary["avg_clv_pct"] is None
    assert summary["result_docs"][0]["official_clv"] is False
    assert summary["result_docs"][0]["accepted_clv"] is True


def test_run_forward_result_refresh_dry_run_marks_timing_and_missing_layers() -> None:
    summary = run_forward_result_refresh(
        forward_bet_docs=[
            {
                "prediction_key": "pred-1",
                "selection_key": "sel-1",
                "tracking_key": "sel-1",
                "match_key": "match-1",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "home",
                "direction": "over",
                "line_value": 4.5,
                "saved_odds": 1.9,
                "saved_at": "2026-07-28T10:05:00Z",
                "match_start_time": "2026-07-28T10:00:00Z",
            },
            {
                "prediction_key": "pred-2",
                "selection_key": "sel-2",
                "tracking_key": "sel-2",
                "match_key": "match-2",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 9.5,
                "saved_odds": 2.1,
            },
        ],
        clv_tracking_docs=[],
        settled_bet_docs=[],
        dry_run=True,
        refreshed_at=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
    )

    assert summary["forward_results"] == 2
    assert summary["status_counts"] == {"excluded": 2}
    assert summary["clv_status_counts"] == {"missing_clv_tracking_record": 2}
    assert summary["settlement_status_counts"] == {"missing_settlement_record": 2}
    assert summary["timing_status_counts"] == {"invalid_after_start": 1, "missing_saved_at": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}
    late_row = next(row for row in summary["result_docs"] if row["prediction_key"] == "pred-1")
    missing_row = next(row for row in summary["result_docs"] if row["prediction_key"] == "pred-2")
    assert late_row["odds_captured_after_start"] is True
    assert late_row["result_loop_status"] == "excluded"
    assert missing_row["timing_status"] == "missing_saved_at"
    assert missing_row["result_loop_status"] == "excluded"


def test_run_forward_result_refresh_excludes_snapshot_created_after_prediction() -> None:
    summary = run_forward_result_refresh(
        forward_bet_docs=[
            {
                "prediction_key": "pred-invalid-timing",
                "selection_key": "sel-invalid-timing",
                "tracking_key": "sel-invalid-timing",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "away",
                "direction": "under",
                "line_value": 5.5,
                "saved_odds": 1.81,
                "odds_snapshot_time": "2026-07-30T00:25:00Z",
                "prediction_created_at": "2026-07-29T23:53:20Z",
                "match_start_time": "2026-07-30T00:30:00Z",
                "invalid_for_model": False,
                "valid_for_forward_evaluation": True,
            }
        ],
        clv_tracking_docs=[],
        settled_bet_docs=[
            {
                "settlement_key": "pred-invalid-timing",
                "prediction_key": "pred-invalid-timing",
                "settlement_status": "settled",
                "settlement_result": "win",
                "pnl_units": 0.81,
                "roi_units": 0.81,
                "stake_units": 1,
            }
        ],
        dry_run=True,
        refreshed_at=datetime(2026, 7, 30, 3, 0, tzinfo=UTC),
    )

    assert summary["timing_status_counts"] == {
        "snapshot_after_prediction_creation": 1
    }
    assert summary["status_counts"] == {"excluded": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}
    assert summary["settled_count"] == 0
    assert summary["pnl_units"] == 0.0
    row = summary["result_docs"][0]
    assert row["result_loop_status"] == "excluded"
    assert row["status_reason"] == "snapshot_after_prediction_creation"
    assert row["pnl_units"] is None
    assert row["roi_units"] is None


def test_run_forward_result_refresh_builds_missing_clv_and_settlement_ephemerally() -> None:
    summary = run_forward_result_refresh(
        forward_bet_docs=[
            {
                "prediction_key": "pred-1",
                "selection_key": "sel-1",
                "tracking_key": "sel-1",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "saved_odds": 2.0,
                "saved_at": "2026-07-28T09:50:00Z",
                "match_start_time": "2026-07-28T10:00:00Z",
                "stake_units": 1,
            }
        ],
        closing_line_docs=[
            {
                "closing_key": "offer-1",
                "offer_key": "offer-1",
                "match_key": "match-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line": 10.5,
                "opening_snapshot_label": "CURRENT",
                "opening_snapshot_time": "2026-07-28T09:50:00Z",
                "opening_over_odds": 2.0,
                "latest_snapshot_label": "T_MINUS_10M",
                "latest_snapshot_time": "2026-07-28T09:55:00Z",
                "latest_over_odds": 1.9,
                "closing_snapshot_label": "T_MINUS_10M",
                "closing_snapshot_time": "2026-07-28T09:55:00Z",
                "closing_over_odds": 1.8,
                "prematch_observation_count": 2,
                "price_history": [{"snapshot_label": "CURRENT", "snapshot_time": "2026-07-28T09:50:00Z", "over_odds": 2.0}],
            }
        ],
        match_stats_canonical=[
            {"match_key": "match-1", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "actual_value": 7},
            {"match_key": "match-1", "stat_key": "cornerKicks", "period": "ALL", "scope": "away", "actual_value": 5},
        ],
        match_results_canonical=[
            {"match_key": "match-1", "home_score": 2, "away_score": 1}
        ],
        dry_run=True,
        refreshed_at=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
    )

    assert summary["ephemeral_clv_rows"] == 1
    assert summary["ephemeral_settled_rows"] == 1
    assert summary["status_counts"] == {"settled": 1}
    assert summary["clv_status_counts"] == {"tracked": 1}
    assert summary["settlement_status_counts"] == {"settled": 1}
    row = summary["result_docs"][0]
    assert row["clv_pct"] == 11.1
    assert row["settlement_result"] == "win"
