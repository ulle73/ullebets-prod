from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class V2OddsCheckpoint:
    key: str
    label: str
    snapshot_type: str
    target_days: int
    min_minutes_to_kickoff: int
    max_minutes_to_kickoff: int


V2_ODDS_CHECKPOINTS = [
    V2OddsCheckpoint(
        key="T_MINUS_3D",
        label="3 dagar fore matchstart",
        snapshot_type="forward",
        target_days=3,
        min_minutes_to_kickoff=60 * 60,
        max_minutes_to_kickoff=84 * 60,
    ),
    V2OddsCheckpoint(
        key="T_MINUS_2D",
        label="2 dagar fore matchstart",
        snapshot_type="forward",
        target_days=2,
        min_minutes_to_kickoff=36 * 60,
        max_minutes_to_kickoff=60 * 60,
    ),
    V2OddsCheckpoint(
        key="T_MINUS_1D",
        label="1 dag fore matchstart",
        snapshot_type="forward",
        target_days=1,
        min_minutes_to_kickoff=18 * 60,
        max_minutes_to_kickoff=36 * 60,
    ),
    V2OddsCheckpoint(
        key="T_MINUS_10M",
        label="10 minuter fore matchstart",
        snapshot_type="closing",
        target_days=0,
        min_minutes_to_kickoff=5,
        max_minutes_to_kickoff=15,
    ),
]


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def get_captured_checkpoint_keys(snapshot_docs: list[dict[str, Any]] | None = None) -> list[str]:
    captured: list[str] = []
    for snapshot in snapshot_docs or []:
        key = snapshot.get("snapshot_label")
        if isinstance(key, str):
            key = key.strip()
        else:
            key = ""
        if key and key not in captured:
            captured.append(key)
    return captured


def pick_due_checkpoint(
    *,
    match_start: Any,
    now: Any | None = None,
    snapshots: list[dict[str, Any]] | None = None,
    checkpoint_filter: str | None = None,
) -> V2OddsCheckpoint | None:
    match_start_dt = _to_datetime(match_start)
    now_dt = _to_datetime(now) or datetime.now(tz=UTC)
    if match_start_dt is None:
        return None

    minutes_to_kickoff = round((match_start_dt - now_dt).total_seconds() / 60)
    if minutes_to_kickoff <= 0:
        return None

    captured = set(get_captured_checkpoint_keys(snapshots))
    for checkpoint in V2_ODDS_CHECKPOINTS:
        if checkpoint_filter and checkpoint.key != checkpoint_filter:
            continue
        if checkpoint.key in captured:
            continue
        if checkpoint.min_minutes_to_kickoff <= minutes_to_kickoff < checkpoint.max_minutes_to_kickoff:
            return checkpoint
    return None


def build_snapshot_timing_fields(
    *,
    match_start: Any,
    snapshot_time: Any,
    checkpoint_key: str | None = None,
    minutes_to_kickoff: int | None = None,
) -> dict[str, Any]:
    snapshot_dt = _to_datetime(snapshot_time) or datetime.now(tz=UTC)
    match_start_dt = _to_datetime(match_start)
    computed_minutes = minutes_to_kickoff
    if computed_minutes is None and match_start_dt is not None:
        computed_minutes = round((match_start_dt - snapshot_dt).total_seconds() / 60)

    checkpoint = next((item for item in V2_ODDS_CHECKPOINTS if item.key == checkpoint_key), None)
    horizon_days = checkpoint.target_days if checkpoint is not None else None
    if horizon_days is None and computed_minutes is not None:
        horizon_days = max(0, round(computed_minutes / MINUTES_PER_DAY))

    invalid_for_model = bool(match_start_dt is not None and snapshot_dt >= match_start_dt)
    return {
        "snapshot_time": snapshot_dt,
        "match_start_time": match_start_dt,
        "minutes_to_kickoff": computed_minutes,
        "horizon_days": horizon_days,
        "invalid_for_model": invalid_for_model,
    }
