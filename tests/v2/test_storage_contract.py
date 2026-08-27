from __future__ import annotations

from ullebets_v2.storage.collections import (
    CANONICAL_COLLECTION_NAMES,
    CLOSING_WATCH_SESSIONS,
)
from ullebets_v2.storage.indexes import build_core_index_plan


def test_closing_watch_sessions_have_canonical_indexes() -> None:
    assert CLOSING_WATCH_SESSIONS in CANONICAL_COLLECTION_NAMES
    plan = next(
        row
        for row in build_core_index_plan()
        if row["collection"] == CLOSING_WATCH_SESSIONS
    )

    assert {
        index["name"]: index for index in plan["indexes"]
    } == {
        "session_key_unique": {
            "keys": [("session_key", 1)],
            "name": "session_key_unique",
            "unique": True,
        },
        "status_lease_expiry": {
            "keys": [("status", 1), ("lease_expires_at", 1)],
            "name": "status_lease_expiry",
        },
    }
