from __future__ import annotations

from datetime import UTC, datetime, timedelta
import math
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError


FORWARD_FIXTURE_STATUSES = frozenset({"", "notstarted", "scheduled"})
T30_ATTEMPT_MINUTES = 35
T10_ATTEMPT_MINUTES = 10
T30_WINDOW_END_MINUTES = 15


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


def _captured_checkpoints(
    *,
    match_key: str,
    match_start_time: datetime,
    snapshot_docs: list[dict[str, Any]],
) -> set[str]:
    captured: set[str] = set()
    for row in snapshot_docs:
        if str(row.get("match_key") or "") != match_key:
            continue
        label = str(row.get("snapshot_label") or "")
        if label not in {"T_MINUS_30M", "T_MINUS_10M"}:
            continue
        if row.get("invalid_for_model") is True:
            continue
        snapshot_time = _to_datetime(row.get("snapshot_time"))
        stored_start = (
            _to_datetime(row.get("match_start_time")) or match_start_time
        )
        if snapshot_time is not None and snapshot_time < stored_start:
            captured.add(label)
    return captured


def _match_plan(
    *,
    fixture: dict[str, Any],
    snapshot_docs: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    match_key = str(fixture["match_key"])
    start_time = fixture["start_time"]
    captured = _captured_checkpoints(
        match_key=match_key,
        match_start_time=start_time,
        snapshot_docs=snapshot_docs,
    )
    has_t30 = "T_MINUS_30M" in captured
    has_t10 = "T_MINUS_10M" in captured

    status: str
    terminal = False
    next_checkpoint: str | None = None
    next_attempt_at: datetime | None = None
    accepted_closing_checkpoint: str | None = None

    if has_t10:
        status = "t10_captured"
        terminal = True
        accepted_closing_checkpoint = "T_MINUS_10M"
    elif now >= start_time:
        terminal = True
        if has_t30:
            status = "t30_captured"
            accepted_closing_checkpoint = "T_MINUS_30M"
        else:
            status = "closing_missed"
    elif has_t30:
        status = "awaiting_t10"
        next_checkpoint = "T_MINUS_10M"
        next_attempt_at = max(
            now,
            start_time - timedelta(minutes=T10_ATTEMPT_MINUTES),
        )
        accepted_closing_checkpoint = "T_MINUS_30M"
    elif now <= start_time - timedelta(minutes=T30_WINDOW_END_MINUTES):
        status = "awaiting_t30"
        next_checkpoint = "T_MINUS_30M"
        next_attempt_at = max(
            now,
            start_time - timedelta(minutes=T30_ATTEMPT_MINUTES),
        )
    else:
        status = "awaiting_t10"
        next_checkpoint = "T_MINUS_10M"
        next_attempt_at = max(
            now,
            start_time - timedelta(minutes=T10_ATTEMPT_MINUTES),
        )

    return {
        "match_key": match_key,
        "start_time": start_time,
        "status": status,
        "terminal": terminal,
        "captured_checkpoints": sorted(captured),
        "accepted_closing_checkpoint": accepted_closing_checkpoint,
        "next_checkpoint": next_checkpoint,
        "next_attempt_at": next_attempt_at,
    }


def build_watch_session_plan(
    *,
    fixture_docs: list[dict[str, Any]],
    snapshot_docs: list[dict[str, Any]],
    now: datetime,
    lookahead_hours: float = 4.0,
) -> dict[str, Any]:
    current_time = _to_datetime(now)
    if current_time is None:
        raise ValueError("now must be a datetime.")
    if lookahead_hours <= 0:
        raise ValueError("lookahead_hours must be positive.")
    window_end = current_time + timedelta(hours=lookahead_hours)

    fixtures: list[dict[str, Any]] = []
    for row in fixture_docs:
        match_key = str(row.get("match_key") or "").strip()
        start_time = _to_datetime(row.get("start_time"))
        status_type = str(row.get("status_type") or "").strip().lower()
        if not match_key or start_time is None:
            continue
        if status_type not in FORWARD_FIXTURE_STATUSES:
            continue
        if start_time > window_end:
            continue
        fixtures.append(
            {**row, "match_key": match_key, "start_time": start_time}
        )
    fixtures.sort(key=lambda row: (row["start_time"], row["match_key"]))

    matches = [
        _match_plan(
            fixture=fixture,
            snapshot_docs=snapshot_docs,
            now=current_time,
        )
        for fixture in fixtures
    ]
    pending = [row for row in matches if not row["terminal"]]
    next_attempts = [
        row["next_attempt_at"]
        for row in pending
        if row.get("next_attempt_at") is not None
    ]
    next_attempt_at = min(next_attempts) if next_attempts else None
    next_wake_seconds = (
        max(
            0,
            math.ceil((next_attempt_at - current_time).total_seconds()),
        )
        if next_attempt_at is not None
        else None
    )
    return {
        "generated_at": current_time,
        "window_end": window_end,
        "lookahead_hours": lookahead_hours,
        "should_watch": bool(pending),
        "match_count": len(matches),
        "pending_match_count": len(pending),
        "terminal_match_count": len(matches) - len(pending),
        "next_attempt_at": next_attempt_at,
        "next_wake_seconds": next_wake_seconds,
        "matches": matches,
    }


def _lease_expiry(*, now: datetime, lease_seconds: int) -> datetime:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive.")
    return now + timedelta(seconds=lease_seconds)


def claim_watch_session(
    *,
    collection: Any,
    session_key: str,
    owner_id: str,
    now: datetime,
    lease_seconds: int = 180,
) -> dict[str, Any] | None:
    current_time = _to_datetime(now)
    if current_time is None:
        raise ValueError("now must be a datetime.")
    if not session_key.strip() or not owner_id.strip():
        raise ValueError("session_key and owner_id must be non-empty.")
    expires_at = _lease_expiry(
        now=current_time,
        lease_seconds=lease_seconds,
    )
    try:
        return collection.find_one_and_update(
            {
                "session_key": session_key,
                "$or": [
                    {"lease_owner": owner_id},
                    {"lease_expires_at": {"$lte": current_time}},
                    {"lease_expires_at": {"$exists": False}},
                ],
            },
            {
                "$setOnInsert": {
                    "session_key": session_key,
                    "created_at": current_time,
                },
                "$set": {
                    "status": "running",
                    "lease_owner": owner_id,
                    "claimed_at": current_time,
                    "last_heartbeat_at": current_time,
                    "lease_expires_at": expires_at,
                    "updated_at": current_time,
                },
                "$inc": {"lease_generation": 1},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        return None


def heartbeat_watch_session(
    *,
    collection: Any,
    session_key: str,
    owner_id: str,
    now: datetime,
    lease_seconds: int = 180,
    state: dict[str, Any],
) -> bool:
    current_time = _to_datetime(now)
    if current_time is None:
        raise ValueError("now must be a datetime.")
    expires_at = _lease_expiry(
        now=current_time,
        lease_seconds=lease_seconds,
    )
    result = collection.update_one(
        {
            "session_key": session_key,
            "lease_owner": owner_id,
            "lease_expires_at": {"$gt": current_time},
        },
        {
            "$set": {
                "state": state,
                "last_heartbeat_at": current_time,
                "lease_expires_at": expires_at,
                "updated_at": current_time,
            }
        },
    )
    return bool(result.matched_count)


def release_watch_session(
    *,
    collection: Any,
    session_key: str,
    owner_id: str,
    now: datetime,
    status: str,
    summary: dict[str, Any],
) -> bool:
    current_time = _to_datetime(now)
    if current_time is None:
        raise ValueError("now must be a datetime.")
    result = collection.update_one(
        {
            "session_key": session_key,
            "lease_owner": owner_id,
            "lease_expires_at": {"$gt": current_time},
        },
        {
            "$set": {
                "status": status,
                "summary": summary,
                "completed_at": current_time,
                "updated_at": current_time,
            },
            "$unset": {
                "lease_owner": "",
                "lease_expires_at": "",
            },
        },
    )
    return bool(result.matched_count)
