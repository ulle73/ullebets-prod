from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace

from pymongo.errors import DuplicateKeyError

from ullebets_v2.closing.session import (
    build_watch_session_plan,
    claim_watch_session,
    heartbeat_watch_session,
    release_watch_session,
)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _fixture(*, match_key: str = "match-1", start: str) -> dict:
    return {
        "match_key": match_key,
        "start_time": _dt(start),
        "status_type": "notstarted",
    }


def _snapshot(*, match_key: str, label: str, start: str) -> dict:
    start_time = _dt(start)
    minutes = 30 if label == "T_MINUS_30M" else 10
    return {
        "match_key": match_key,
        "snapshot_label": label,
        "snapshot_time": start_time - timedelta(minutes=minutes),
        "match_start_time": start_time,
        "invalid_for_model": False,
    }


def _matches(row: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(row, option) for option in expected):
                return False
            continue
        value = row.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected:
                if (key in row) is not bool(expected["$exists"]):
                    return False
            if "$lte" in expected and not (
                value is not None and value <= expected["$lte"]
            ):
                return False
            if "$gt" in expected and not (
                value is not None and value > expected["$gt"]
            ):
                return False
        elif value != expected:
            return False
    return True


def _apply_update(row: dict, update: dict, *, inserted: bool) -> None:
    if inserted:
        row.update(deepcopy(update.get("$setOnInsert", {})))
    row.update(deepcopy(update.get("$set", {})))
    for key, increment in update.get("$inc", {}).items():
        row[key] = row.get(key, 0) + increment
    for key in update.get("$unset", {}):
        row.pop(key, None)


class AtomicSessionCollection:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def find_one_and_update(
        self,
        query: dict,
        update: dict,
        *,
        upsert: bool,
        return_document: object,
    ) -> dict | None:
        del return_document
        session_key = str(query["session_key"])
        row = self.rows.get(session_key)
        if row is not None and _matches(row, query):
            _apply_update(row, update, inserted=False)
            return deepcopy(row)
        if not upsert:
            return None
        if row is not None:
            raise DuplicateKeyError("session_key_unique")
        inserted = {"session_key": session_key}
        _apply_update(inserted, update, inserted=True)
        self.rows[session_key] = inserted
        return deepcopy(inserted)

    def update_one(self, query: dict, update: dict) -> SimpleNamespace:
        session_key = str(query["session_key"])
        row = self.rows.get(session_key)
        if row is None or not _matches(row, query):
            return SimpleNamespace(matched_count=0)
        _apply_update(row, update, inserted=False)
        return SimpleNamespace(matched_count=1)


def test_watch_plan_activates_before_t30_attempt() -> None:
    plan = build_watch_session_plan(
        fixture_docs=[_fixture(start="2026-08-27T18:00:00Z")],
        snapshot_docs=[],
        now=_dt("2026-08-27T14:00:00Z"),
        lookahead_hours=4.0,
    )

    assert plan["should_watch"] is True
    assert plan["next_wake_seconds"] == 12_300
    assert plan["matches"][0]["status"] == "awaiting_t30"
    assert plan["matches"][0]["next_checkpoint"] == "T_MINUS_30M"
    assert plan["matches"][0]["next_attempt_at"] == _dt(
        "2026-08-27T17:25:00Z"
    )


def test_watch_plan_moves_from_t30_to_t10_and_sorts_multiple_kickoffs() -> None:
    plan = build_watch_session_plan(
        fixture_docs=[
            _fixture(match_key="later", start="2026-08-27T19:00:00Z"),
            _fixture(match_key="first", start="2026-08-27T18:00:00Z"),
        ],
        snapshot_docs=[
            _snapshot(
                match_key="first",
                label="T_MINUS_30M",
                start="2026-08-27T18:00:00Z",
            )
        ],
        now=_dt("2026-08-27T17:31:00Z"),
        lookahead_hours=2.0,
    )

    assert [row["match_key"] for row in plan["matches"]] == ["first", "later"]
    assert plan["matches"][0]["status"] == "awaiting_t10"
    assert plan["matches"][0]["next_checkpoint"] == "T_MINUS_10M"
    assert plan["matches"][0]["next_attempt_at"] == _dt(
        "2026-08-27T17:50:00Z"
    )
    assert plan["next_wake_seconds"] == 1_140


def test_watch_plan_t10_is_terminal() -> None:
    start = "2026-08-27T18:00:00Z"
    plan = build_watch_session_plan(
        fixture_docs=[_fixture(start=start)],
        snapshot_docs=[
            _snapshot(match_key="match-1", label="T_MINUS_10M", start=start)
        ],
        now=_dt("2026-08-27T17:51:00Z"),
        lookahead_hours=1.0,
    )

    assert plan["should_watch"] is False
    assert plan["next_wake_seconds"] is None
    assert plan["matches"][0]["status"] == "t10_captured"
    assert plan["matches"][0]["terminal"] is True


def test_watch_plan_marks_t30_only_as_accepted_at_kickoff() -> None:
    start = "2026-08-27T18:00:00Z"
    plan = build_watch_session_plan(
        fixture_docs=[_fixture(start=start)],
        snapshot_docs=[
            _snapshot(match_key="match-1", label="T_MINUS_30M", start=start)
        ],
        now=_dt("2026-08-27T18:00:00Z"),
        lookahead_hours=1.0,
    )

    assert plan["should_watch"] is False
    assert plan["matches"][0]["status"] == "t30_captured"
    assert plan["matches"][0]["accepted_closing_checkpoint"] == (
        "T_MINUS_30M"
    )


def test_watch_plan_marks_missing_both_at_kickoff() -> None:
    plan = build_watch_session_plan(
        fixture_docs=[_fixture(start="2026-08-27T18:00:00Z")],
        snapshot_docs=[],
        now=_dt("2026-08-27T18:00:00Z"),
        lookahead_hours=1.0,
    )

    assert plan["should_watch"] is False
    assert plan["matches"][0]["status"] == "closing_missed"
    assert plan["matches"][0]["terminal"] is True


def test_watch_session_lease_claim_heartbeat_takeover_and_fencing() -> None:
    collection = AtomicSessionCollection()
    now = _dt("2026-08-27T14:00:00Z")

    first = claim_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-a",
        now=now,
        lease_seconds=180,
    )
    blocked = claim_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-b",
        now=now + timedelta(seconds=30),
        lease_seconds=180,
    )
    heartbeat = heartbeat_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-a",
        now=now + timedelta(seconds=60),
        lease_seconds=180,
        state={"next_checkpoint": "T_MINUS_30M"},
    )

    assert first is not None
    assert first["lease_owner"] == "runner-a"
    assert first["lease_expires_at"] == now + timedelta(seconds=180)
    assert first["lease_generation"] == 1
    assert blocked is None
    assert heartbeat is True
    assert collection.rows["closing:2026-08-27"]["state"] == {
        "next_checkpoint": "T_MINUS_30M"
    }
    assert collection.rows["closing:2026-08-27"]["lease_expires_at"] == (
        now + timedelta(seconds=240)
    )

    takeover_at = now + timedelta(seconds=241)
    replacement = claim_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-b",
        now=takeover_at,
        lease_seconds=180,
    )
    stale_heartbeat = heartbeat_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-a",
        now=takeover_at + timedelta(seconds=1),
        lease_seconds=180,
        state={"stale": True},
    )
    stale_release = release_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-a",
        now=takeover_at + timedelta(seconds=1),
        status="completed",
        summary={"stale": True},
    )

    assert replacement is not None
    assert replacement["lease_owner"] == "runner-b"
    assert replacement["lease_generation"] == 2
    assert stale_heartbeat is False
    assert stale_release is False
    assert collection.rows["closing:2026-08-27"]["lease_owner"] == (
        "runner-b"
    )


def test_watch_session_release_is_terminal_and_clears_lease() -> None:
    collection = AtomicSessionCollection()
    now = _dt("2026-08-27T14:00:00Z")
    claim_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-a",
        now=now,
        lease_seconds=180,
    )

    released = release_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-a",
        now=now + timedelta(seconds=30),
        status="completed",
        summary={"t10_captured_matches": 1},
    )
    row = collection.rows["closing:2026-08-27"]

    assert released is True
    assert row["status"] == "completed"
    assert row["summary"] == {"t10_captured_matches": 1}
    assert row["completed_at"] == now + timedelta(seconds=30)
    assert "lease_owner" not in row
    assert "lease_expires_at" not in row


def test_expired_owner_cannot_heartbeat_without_reclaiming() -> None:
    collection = AtomicSessionCollection()
    now = _dt("2026-08-27T14:00:00Z")
    claim_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-a",
        now=now,
        lease_seconds=60,
    )

    assert heartbeat_watch_session(
        collection=collection,
        session_key="closing:2026-08-27",
        owner_id="runner-a",
        now=now + timedelta(seconds=61),
        lease_seconds=60,
        state={},
    ) is False
