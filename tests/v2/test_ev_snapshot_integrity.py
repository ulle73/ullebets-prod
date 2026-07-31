from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.ev_model.snapshot_integrity import (
    build_missing_closing_clv_update,
    detect_simulated_capture_runs,
    select_simulated_capture_snapshots,
)


def test_detect_simulated_capture_runs_uses_job_wall_clock() -> None:
    rows = [
        {
            "run_id": "real",
            "job_name": "capture_odds_checkpoints",
            "source_workflow": "run-unibet-odds-checkpoints.yml",
            "started_at": datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            "target_window": {
                "captured_at": "2026-01-01T10:01:00+00:00"
            },
        },
        {
            "run_id": "simulated",
            "job_name": "capture_closing_snapshots",
            "source_workflow": "run-unibet-closing.yml",
            "started_at": datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            "target_window": {
                "captured_at": "2026-01-02T10:00:00+00:00"
            },
        },
    ]

    detected = detect_simulated_capture_runs(
        rows,
        tolerance_minutes=5,
    )

    assert [row["run_id"] for row in detected] == ["simulated"]
    assert detected[0]["clock_drift_minutes"] == 1440.0


def test_select_simulated_capture_snapshots_dedupes_duplicate_runs() -> None:
    captured_at = datetime(2026, 1, 2, 10, 0, tzinfo=UTC)
    simulated_runs = [
        {
            "run_id": "run-a",
            "source_workflow": "closing.yml",
            "captured_at": captured_at,
        },
        {
            "run_id": "run-b",
            "source_workflow": "closing.yml",
            "captured_at": captured_at,
        },
    ]
    snapshots = [
        {
            "snapshot_key": "invalid",
            "source_workflow": "closing.yml",
            "captured_at": captured_at,
            "offer_key": "offer-1",
        },
        {
            "snapshot_key": "valid",
            "source_workflow": "closing.yml",
            "captured_at": datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            "offer_key": "offer-1",
        },
    ]

    selected = select_simulated_capture_snapshots(
        snapshot_docs=snapshots,
        simulated_runs=simulated_runs,
    )

    assert [row["snapshot_key"] for row in selected] == ["invalid"]
    assert selected[0]["invalidation_source_run_ids"] == [
        "run-a",
        "run-b",
    ]


def test_build_missing_closing_clv_update_clears_derived_values() -> None:
    now = datetime(2026, 1, 2, 10, 0, tzinfo=UTC)

    update = build_missing_closing_clv_update(invalidated_at=now)

    assert update["$set"]["clv_status"] == "missing_closing_line"
    assert update["$set"]["clv_pct"] is None
    assert update["$set"]["beat_closing_line"] is None
    assert "invalid_for_model" not in update["$set"]
    assert update["$set"]["closing_invalidation_reason"] == (
        "simulated_time_override"
    )
