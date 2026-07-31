from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def detect_simulated_capture_runs(
    job_runs: list[dict[str, Any]],
    *,
    tolerance_minutes: float = 5.0,
) -> list[dict[str, Any]]:
    detected: list[dict[str, Any]] = []
    for row in job_runs:
        target_window = (
            row.get("target_window")
            if isinstance(row.get("target_window"), dict)
            else {}
        )
        captured_at = _to_datetime(target_window.get("captured_at"))
        started_at = _to_datetime(row.get("started_at"))
        if captured_at is None or started_at is None:
            continue
        drift_minutes = (
            captured_at - started_at
        ).total_seconds() / 60.0
        if abs(drift_minutes) <= tolerance_minutes:
            continue
        detected.append(
            {
                "run_id": str(row.get("run_id") or ""),
                "job_name": str(row.get("job_name") or ""),
                "source_workflow": str(row.get("source_workflow") or ""),
                "started_at": started_at,
                "captured_at": captured_at,
                "clock_drift_minutes": round(drift_minutes, 6),
            }
        )
    return detected


def select_simulated_capture_snapshots(
    *,
    snapshot_docs: list[dict[str, Any]],
    simulated_runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    run_ids_by_capture: dict[tuple[str, datetime], set[str]] = {}
    for row in simulated_runs:
        source_workflow = str(row.get("source_workflow") or "")
        captured_at = _to_datetime(row.get("captured_at"))
        if not source_workflow or captured_at is None:
            continue
        capture_key = (source_workflow, captured_at)
        run_id = str(row.get("run_id") or "")
        if run_id:
            run_ids_by_capture.setdefault(capture_key, set()).add(run_id)

    selected_by_key: dict[str, dict[str, Any]] = {}
    for row in snapshot_docs:
        source_workflow = str(row.get("source_workflow") or "")
        captured_at = _to_datetime(row.get("captured_at"))
        if captured_at is None:
            captured_at = _to_datetime(row.get("snapshot_time"))
        run_ids = run_ids_by_capture.get((source_workflow, captured_at))
        snapshot_key = str(row.get("snapshot_key") or "")
        if not run_ids or not snapshot_key:
            continue
        selected_by_key[snapshot_key] = {
            **row,
            "invalidation_source_run_ids": sorted(run_ids),
        }
    return [
        selected_by_key[key]
        for key in sorted(selected_by_key)
    ]


def build_missing_closing_clv_update(
    *,
    invalidated_at: datetime,
) -> dict[str, dict[str, Any]]:
    return {
        "$set": {
            "clv_status": "missing_closing_line",
            "opening_snapshot_label": None,
            "opening_snapshot_time": None,
            "opening_odds": None,
            "latest_snapshot_label": None,
            "latest_snapshot_time": None,
            "latest_observed_odds": None,
            "closing_snapshot_label": None,
            "closing_snapshot_time": None,
            "closing_odds": None,
            "opening_observed_at": None,
            "latest_observed_at": None,
            "closing_observed_at": None,
            "price_history": [],
            "prematch_observation_count": 0,
            "clv_pct": None,
            "implied_edge_delta": None,
            "beat_closing_line": None,
            "closing_invalidation_reason": (
                "simulated_time_override"
            ),
            "closing_invalidated_at": invalidated_at,
            "refreshed_at": invalidated_at,
        }
    }
