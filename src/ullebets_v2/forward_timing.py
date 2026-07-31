from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def to_utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if abs(timestamp) >= 100_000_000_000:
            timestamp /= 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def evaluate_forward_timing(row: dict[str, Any]) -> dict[str, Any]:
    match_start_time = to_utc_datetime(
        row.get("match_start_time")
        or row.get("scheduled_start")
        or row.get("start_time")
        or row.get("eventTimestampMs")
    )
    uses_frozen_prediction_contract = (
        row.get("odds_snapshot_time") is not None
        or row.get("prediction_created_at") is not None
    )

    if uses_frozen_prediction_contract:
        observation_time = to_utc_datetime(row.get("odds_snapshot_time"))
        prediction_created_at = to_utc_datetime(
            row.get("prediction_created_at")
        )
        timing_contract = "frozen_prediction"
        if observation_time is None:
            timing_status = "missing_snapshot_time"
        elif prediction_created_at is None:
            timing_status = "missing_prediction_created_at"
        elif match_start_time is None:
            timing_status = "missing_match_start"
        elif observation_time > prediction_created_at:
            timing_status = "snapshot_after_prediction_creation"
        elif observation_time >= match_start_time:
            timing_status = "snapshot_at_or_after_match_start"
        elif prediction_created_at >= match_start_time:
            timing_status = "prediction_at_or_after_match_start"
        elif bool(row.get("invalid_for_model")):
            timing_status = "invalid_for_model_flag"
        elif row.get("valid_for_forward_evaluation") is False:
            timing_status = "forward_evaluation_disabled"
        else:
            timing_status = "prematch_valid"
    else:
        observation_time = to_utc_datetime(
            row.get("saved_at")
            or row.get("snapshot_time")
            or row.get("savedOddsObservedAt")
            or row.get("trackedAt")
            or row.get("createdAt")
        )
        prediction_created_at = observation_time
        timing_contract = "saved_observation"
        if observation_time is None:
            timing_status = "missing_saved_at"
        elif match_start_time is None:
            timing_status = "missing_match_start"
        elif observation_time >= match_start_time:
            timing_status = "invalid_after_start"
        elif bool(row.get("invalid_for_model")):
            timing_status = "invalid_for_model_flag"
        elif row.get("valid_for_forward_evaluation") is False:
            timing_status = "forward_evaluation_disabled"
        else:
            timing_status = "prematch_valid"

    valid_for_performance = timing_status == "prematch_valid"
    return {
        "timing_contract": timing_contract,
        "timing_status": timing_status,
        "observation_time": observation_time,
        "prediction_created_at": prediction_created_at,
        "match_start_time": match_start_time,
        "valid_for_performance": valid_for_performance,
    }
