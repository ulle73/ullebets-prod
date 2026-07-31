from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ullebets_v2.closing.watch import build_closing_watch_plan


def _fixture(now: datetime, *, hours: float = 1.0) -> dict:
    return {
        "match_key": "match-1",
        "start_time": now + timedelta(hours=hours),
        "status_type": "notstarted",
    }


def test_closing_watch_disables_when_no_fixture_is_close() -> None:
    now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    plan = build_closing_watch_plan(
        fixture_docs=[_fixture(now, hours=3)],
        snapshot_docs=[],
        now=now,
        lookahead_hours=2,
    )

    assert plan["should_enable"] is False
    assert plan["action"] == "disable"
    assert plan["reason"] == "no_upcoming_fixtures_within_watch_window"


def test_closing_watch_enables_for_uncaptured_upcoming_fixture() -> None:
    now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    plan = build_closing_watch_plan(
        fixture_docs=[_fixture(now)],
        snapshot_docs=[],
        now=now,
        lookahead_hours=2,
    )

    assert plan["should_enable"] is True
    assert plan["pending_fixture_count"] == 1
    assert plan["next_pending_match_key"] == "match-1"


def test_closing_watch_disables_when_valid_t10_is_already_captured() -> None:
    now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    fixture = _fixture(now)

    plan = build_closing_watch_plan(
        fixture_docs=[fixture],
        snapshot_docs=[
            {
                "match_key": "match-1",
                "snapshot_label": "T_MINUS_10M",
                "snapshot_time": fixture["start_time"] - timedelta(minutes=10),
                "match_start_time": fixture["start_time"],
                "invalid_for_model": False,
            }
        ],
        now=now,
        lookahead_hours=2,
    )

    assert plan["should_enable"] is False
    assert plan["captured_fixture_count"] == 1
    assert plan["reason"] == "all_upcoming_fixtures_have_valid_closing_snapshots"


def test_closing_watch_keeps_retrying_after_invalid_t10_snapshot() -> None:
    now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    fixture = _fixture(now)

    plan = build_closing_watch_plan(
        fixture_docs=[fixture],
        snapshot_docs=[
            {
                "match_key": "match-1",
                "snapshot_label": "T_MINUS_10M",
                "snapshot_time": fixture["start_time"],
                "match_start_time": fixture["start_time"],
                "invalid_for_model": True,
            }
        ],
        now=now,
        lookahead_hours=2,
    )

    assert plan["should_enable"] is True
    assert plan["pending_fixture_count"] == 1
