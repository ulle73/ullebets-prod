from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.forward_v2.watch_closing_window import run_watch_session
from ullebets_v2.closing.session import build_watch_session_plan
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


class FakeClock:
    def __init__(self, value: datetime) -> None:
        self.value = value
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += timedelta(seconds=seconds)


class CaptureHarness:
    def __init__(
        self,
        *,
        start_time: datetime,
        snapshots: list[dict] | None = None,
        fail_first: bool = False,
        always_empty: bool = False,
    ) -> None:
        self.start_time = start_time
        self.snapshots = list(snapshots or [])
        self.fail_first = fail_first
        self.always_empty = always_empty
        self.calls: list[datetime] = []
        self.post_capture_calls: list[tuple[dict, datetime]] = []

    def load_plan(self, *, database: object, now: datetime, lookahead_hours: float) -> dict:
        del database
        return build_watch_session_plan(
            fixture_docs=[
                {
                    "match_key": "match-1",
                    "start_time": self.start_time,
                    "status_type": "notstarted",
                }
            ],
            snapshot_docs=self.snapshots,
            now=now,
            lookahead_hours=lookahead_hours,
        )

    def capture(self, captured_at: datetime) -> dict:
        self.calls.append(captured_at)
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("temporary provider failure")
        if self.always_empty:
            return {
                "market_snapshot_upserts": 0,
                "due_targets": [{"match_key": "match-1"}],
            }
        minutes = round(
            (self.start_time - captured_at).total_seconds() / 60
        )
        label = "T_MINUS_30M" if minutes >= 15 else "T_MINUS_10M"
        self.snapshots.append(
            {
                "match_key": "match-1",
                "snapshot_label": label,
                "snapshot_time": captured_at,
                "match_start_time": self.start_time,
                "invalid_for_model": False,
            }
        )
        return {
            "market_snapshot_upserts": 1,
            "due_targets": [{"match_key": "match-1"}],
        }

    def post_capture(self, summary: dict, captured_at: datetime) -> dict:
        self.post_capture_calls.append((summary, captured_at))
        return {"status": "scored"}


def _lease_doubles(*, heartbeat_values: list[bool] | None = None) -> dict:
    values = list(heartbeat_values or [True])
    events: list[str] = []

    def claim(**kwargs: object) -> dict:
        del kwargs
        events.append("claim")
        return {"lease_owner": "runner-1"}

    def heartbeat(**kwargs: object) -> bool:
        del kwargs
        events.append("heartbeat")
        return values.pop(0) if values else True

    def release(**kwargs: object) -> bool:
        del kwargs
        events.append("release")
        return True

    return {
        "claim_session": claim,
        "heartbeat_session": heartbeat,
        "release_session": release,
        "events": events,
    }


def test_watch_session_captures_t30_then_t10_on_runner_clock() -> None:
    clock = FakeClock(datetime(2026, 8, 27, 14, 0, tzinfo=UTC))
    harness = CaptureHarness(
        start_time=datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
    )
    leases = _lease_doubles()

    summary = run_watch_session(
        database={},
        owner_id="runner-1",
        now=clock.now,
        sleep=clock.sleep,
        capture=harness.capture,
        post_capture=harness.post_capture,
        load_plan=harness.load_plan,
        lookahead_hours=4.0,
        max_session_seconds=3_600,
        poll_seconds=60,
        **{key: value for key, value in leases.items() if key != "events"},
    )

    assert harness.calls == [
        datetime(2026, 8, 27, 14, 25, tzinfo=UTC),
        datetime(2026, 8, 27, 14, 50, tzinfo=UTC),
    ]
    assert summary["status"] == "completed"
    assert summary["t30_captured_matches"] == 1
    assert summary["t10_captured_matches"] == 1
    assert summary["capture_attempts"] == 2
    assert [row[1] for row in harness.post_capture_calls] == harness.calls
    assert leases["events"][0] == "claim"
    assert leases["events"][-1] == "release"


def test_watch_session_restart_after_t30_targets_only_t10() -> None:
    start_time = datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
    clock = FakeClock(datetime(2026, 8, 27, 14, 35, tzinfo=UTC))
    harness = CaptureHarness(
        start_time=start_time,
        snapshots=[
            {
                "match_key": "match-1",
                "snapshot_label": "T_MINUS_30M",
                "snapshot_time": start_time - timedelta(minutes=30),
                "match_start_time": start_time,
                "invalid_for_model": False,
            }
        ],
    )
    leases = _lease_doubles()

    summary = run_watch_session(
        database={},
        owner_id="runner-1",
        now=clock.now,
        sleep=clock.sleep,
        capture=harness.capture,
        load_plan=harness.load_plan,
        max_session_seconds=1_800,
        poll_seconds=60,
        **{key: value for key, value in leases.items() if key != "events"},
    )

    assert harness.calls == [datetime(2026, 8, 27, 14, 50, tzinfo=UTC)]
    assert summary["t10_captured_matches"] == 1


def test_watch_session_retries_transient_capture_error() -> None:
    clock = FakeClock(datetime(2026, 8, 27, 14, 25, tzinfo=UTC))
    harness = CaptureHarness(
        start_time=datetime(2026, 8, 27, 15, 0, tzinfo=UTC),
        fail_first=True,
    )
    leases = _lease_doubles()

    summary = run_watch_session(
        database={},
        owner_id="runner-1",
        now=clock.now,
        sleep=clock.sleep,
        capture=harness.capture,
        load_plan=harness.load_plan,
        max_session_seconds=2_000,
        poll_seconds=60,
        **{key: value for key, value in leases.items() if key != "events"},
    )

    assert len(harness.calls) == 3
    assert summary["capture_errors"] == 1
    assert summary["t30_captured_matches"] == 1
    assert summary["t10_captured_matches"] == 1


def test_watch_session_valid_empty_capture_stays_bounded() -> None:
    clock = FakeClock(datetime(2026, 8, 27, 14, 25, tzinfo=UTC))
    harness = CaptureHarness(
        start_time=datetime(2026, 8, 27, 15, 0, tzinfo=UTC),
        always_empty=True,
    )
    leases = _lease_doubles()

    summary = run_watch_session(
        database={},
        owner_id="runner-1",
        now=clock.now,
        sleep=clock.sleep,
        capture=harness.capture,
        load_plan=harness.load_plan,
        max_session_seconds=120,
        poll_seconds=60,
        **{key: value for key, value in leases.items() if key != "events"},
    )

    assert summary["status"] == "bounded_runtime_reached"
    assert summary["valid_empty_captures"] == 2
    assert clock.value == datetime(2026, 8, 27, 14, 27, tzinfo=UTC)


def test_watch_session_stops_when_lease_is_lost() -> None:
    clock = FakeClock(datetime(2026, 8, 27, 14, 25, tzinfo=UTC))
    harness = CaptureHarness(
        start_time=datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
    )
    leases = _lease_doubles(heartbeat_values=[False])

    summary = run_watch_session(
        database={},
        owner_id="runner-1",
        now=clock.now,
        sleep=clock.sleep,
        capture=harness.capture,
        load_plan=harness.load_plan,
        max_session_seconds=120,
        poll_seconds=60,
        **{key: value for key, value in leases.items() if key != "events"},
    )

    assert summary["status"] == "lease_lost"
    assert harness.calls == []
    assert "release" not in leases["events"]


def test_watch_session_dry_run_never_claims_sleeps_or_captures() -> None:
    clock = FakeClock(datetime(2026, 8, 27, 14, 0, tzinfo=UTC))
    harness = CaptureHarness(
        start_time=datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
    )

    def forbidden(**kwargs: object) -> object:
        raise AssertionError(f"unexpected mutating call: {kwargs}")

    summary = run_watch_session(
        database={},
        owner_id="dry-run",
        now=clock.now,
        sleep=clock.sleep,
        capture=harness.capture,
        load_plan=harness.load_plan,
        max_session_seconds=60,
        poll_seconds=1,
        dry_run=True,
        claim_session=forbidden,
        heartbeat_session=forbidden,
        release_session=forbidden,
    )

    assert summary["status"] == "dry_run"
    assert harness.calls == []
    assert clock.sleeps == []
