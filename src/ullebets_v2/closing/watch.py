from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ullebets_v2.storage.collections import FIXTURES_CANONICAL, MARKET_SNAPSHOTS


FORWARD_FIXTURE_STATUSES = frozenset({"", "notstarted", "scheduled"})


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


def _status_is_forward(value: Any) -> bool:
    return str(value or "").strip().lower() in FORWARD_FIXTURE_STATUSES


def _has_valid_closing_snapshot(
    *,
    match_key: str,
    match_start_time: datetime,
    snapshot_docs: list[dict[str, Any]],
) -> bool:
    for row in snapshot_docs:
        if str(row.get("match_key") or "") != match_key:
            continue
        if row.get("snapshot_label") != "T_MINUS_10M":
            continue
        if row.get("invalid_for_model") is True:
            continue
        snapshot_time = _to_datetime(row.get("snapshot_time"))
        stored_start_time = _to_datetime(row.get("match_start_time")) or match_start_time
        if snapshot_time is not None and snapshot_time < stored_start_time:
            return True
    return False


def build_closing_watch_plan(
    *,
    fixture_docs: list[dict[str, Any]],
    snapshot_docs: list[dict[str, Any]],
    now: datetime,
    lookahead_hours: float = 2.0,
) -> dict[str, Any]:
    current_time = _to_datetime(now)
    if current_time is None:
        raise ValueError("now must be a timezone-aware datetime.")
    if lookahead_hours <= 0:
        raise ValueError("lookahead_hours must be positive.")
    window_end = current_time + timedelta(hours=lookahead_hours)

    upcoming: list[dict[str, Any]] = []
    for row in fixture_docs:
        start_time = _to_datetime(row.get("start_time"))
        match_key = str(row.get("match_key") or "").strip()
        if not match_key or start_time is None:
            continue
        if not _status_is_forward(row.get("status_type")):
            continue
        if current_time < start_time <= window_end:
            upcoming.append({**row, "match_key": match_key, "start_time": start_time})
    upcoming.sort(key=lambda row: (row["start_time"], row["match_key"]))

    pending = [
        row
        for row in upcoming
        if not _has_valid_closing_snapshot(
            match_key=row["match_key"],
            match_start_time=row["start_time"],
            snapshot_docs=snapshot_docs,
        )
    ]
    should_enable = bool(pending)
    if pending:
        reason = "uncaptured_fixture_within_watch_window"
    elif upcoming:
        reason = "all_upcoming_fixtures_have_valid_closing_snapshots"
    else:
        reason = "no_upcoming_fixtures_within_watch_window"

    return {
        "generated_at": current_time.isoformat(),
        "window_end": window_end.isoformat(),
        "lookahead_hours": lookahead_hours,
        "action": "enable" if should_enable else "disable",
        "should_enable": should_enable,
        "reason": reason,
        "upcoming_fixture_count": len(upcoming),
        "pending_fixture_count": len(pending),
        "captured_fixture_count": len(upcoming) - len(pending),
        "next_pending_match_key": pending[0]["match_key"] if pending else None,
        "next_pending_start_time": pending[0]["start_time"].isoformat() if pending else None,
    }


def load_closing_watch_plan(
    *,
    database: Any,
    now: datetime,
    lookahead_hours: float = 2.0,
) -> dict[str, Any]:
    window_end = now + timedelta(hours=lookahead_hours)
    fixture_docs = list(
        database[FIXTURES_CANONICAL].find(
            {"start_time": {"$gt": now, "$lte": window_end}},
            projection={"_id": 0},
        )
    )
    match_keys = [str(row.get("match_key")) for row in fixture_docs if row.get("match_key")]
    snapshot_docs = (
        list(
            database[MARKET_SNAPSHOTS].find(
                {
                    "match_key": {"$in": match_keys},
                    "snapshot_label": "T_MINUS_10M",
                },
                projection={"_id": 0},
            )
        )
        if match_keys
        else []
    )
    return build_closing_watch_plan(
        fixture_docs=fixture_docs,
        snapshot_docs=snapshot_docs,
        now=now,
        lookahead_hours=lookahead_hours,
    )
