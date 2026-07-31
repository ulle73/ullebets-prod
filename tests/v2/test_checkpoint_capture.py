from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ullebets_v2.checkpoints.policy import build_snapshot_timing_fields, pick_due_checkpoint
from ullebets_v2.checkpoints.service import run_checkpoint_capture, select_due_checkpoint_targets

from tests.v2.test_odds_ingest import (
    FakeHistoricalCollection,
    FakeHistoricalDatabase,
    FakeOracle,
    build_legacy_backtest_doc,
    build_support_docs,
    fake_transport,
)


def test_pick_due_checkpoint_uses_v2_policy_windows() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)

    assert pick_due_checkpoint(match_start=now + timedelta(hours=72), now=now).key == "T_MINUS_3D"
    assert pick_due_checkpoint(match_start=now + timedelta(hours=48), now=now).key == "T_MINUS_2D"
    assert pick_due_checkpoint(match_start=now + timedelta(hours=24), now=now).key == "T_MINUS_1D"
    assert pick_due_checkpoint(match_start=now + timedelta(hours=12), now=now).key == "T_MINUS_12H"
    assert pick_due_checkpoint(match_start=now + timedelta(hours=2), now=now).key == "T_MINUS_2H"
    assert pick_due_checkpoint(match_start=now + timedelta(minutes=10), now=now).key == "T_MINUS_10M"
    assert pick_due_checkpoint(match_start=now - timedelta(minutes=1), now=now) is None


def test_select_due_checkpoint_targets_skips_already_captured_snapshot_label() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)
    targets = [
        {
            "match_key": "match-1",
            "league_key": "premier-league",
            "league_name": "Premier League",
            "home_team_name": "Arsenal",
            "away_team_name": "Bournemouth",
            "start_time": now + timedelta(hours=48),
        }
    ]
    due = select_due_checkpoint_targets(
        targets=targets,
        now=now,
        existing_snapshot_docs=[{"match_key": "match-1", "snapshot_label": "T_MINUS_2D"}],
    )

    assert due == []


def test_select_due_checkpoint_targets_can_reserve_t_minus_10m_for_closing_job() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)
    due = select_due_checkpoint_targets(
        targets=[
            {
                "match_key": "match-1",
                "start_time": now + timedelta(minutes=10),
            }
        ],
        now=now,
        excluded_checkpoint_keys={"T_MINUS_10M"},
    )

    assert due == []


def test_pick_due_checkpoint_ignores_invalid_snapshot_label() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)

    due = pick_due_checkpoint(
        match_start=now + timedelta(minutes=10),
        now=now,
        snapshots=[
            {
                "snapshot_label": "T_MINUS_10M",
                "invalid_for_model": True,
            }
        ],
    )

    assert due is not None
    assert due.key == "T_MINUS_10M"


def test_build_snapshot_timing_fields_marks_post_start_rows_invalid() -> None:
    timing = build_snapshot_timing_fields(
        match_start="2026-06-22T10:00:00Z",
        snapshot_time="2026-06-22T10:00:00Z",
        checkpoint_key="T_MINUS_10M",
    )

    assert timing["invalid_for_model"] is True
    assert timing["minutes_to_kickoff"] == 0
    assert timing["horizon_days"] == 0


def test_run_checkpoint_capture_dry_run_builds_market_snapshots() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)

    def checkpoint_transport(url: str, headers: dict[str, str], timeout_seconds: int):  # noqa: ARG001
        class Response:
            def __init__(self, status: int, data: dict) -> None:
                self.status = status
                self.data = data
                self.headers = {}

        if "betoffer/event/" in url:
            return fake_transport(url, headers, timeout_seconds)
        return Response(
            200,
            {
                "events": [
                    {
                        "event": {
                            "id": "evt-1",
                            "homeName": "Arsenal",
                            "awayName": "Bournemouth",
                            "start": (now + timedelta(hours=48)).isoformat().replace("+00:00", "Z"),
                            "group": "Premier League",
                        }
                    }
                ]
            },
        )

    summary = run_checkpoint_capture(
        targets=[
            {
                "match_key": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": now + timedelta(hours=48),
            }
        ],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-odds-checkpoints.yml",
        dry_run=True,
        transport=checkpoint_transport,
        oracle=FakeOracle(),
        now=now,
    )

    assert summary["due_matches"] == 1
    assert summary["checkpoint_counts"] == {"T_MINUS_2D": 1}
    assert summary["matched_events"] == 1
    assert summary["market_snapshots"] == 1
    assert summary["invalid_for_model_rows"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_checkpoint_capture_dry_run_handles_empty_due_window() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)
    summary = run_checkpoint_capture(
        targets=[],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-odds-checkpoints.yml",
        dry_run=True,
        now=now,
    )

    assert summary["target_matches"] == 0
    assert summary["due_matches"] == 0
    assert summary["market_snapshots"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_checkpoint_capture_replays_historical_v2_windows_without_live_fetch() -> None:
    historical_database = FakeHistoricalDatabase()
    historical_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc(with_snapshots=True)])

    def failing_transport(url: str, headers: dict[str, str], timeout_seconds: int):  # noqa: ARG001
        raise AssertionError(f"live transport should not be used in replay mode: {url}")

    summary = run_checkpoint_capture(
        targets=[
            {
                "match_key": "match-legacy-checkpoints",
                "source_match_id": 14689178,
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2025, 10, 8, 18, 0, tzinfo=UTC),
                "source_date": "2025-10-08",
            }
        ],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-odds-checkpoints.yml",
        dry_run=True,
        transport=failing_transport,
        legacy_backtest_database=historical_database,
    )

    assert summary["target_matches"] == 1
    assert summary["due_matches"] == 4
    assert summary["checkpoint_counts"] == {
        "T_MINUS_10M": 1,
        "T_MINUS_12H": 1,
        "T_MINUS_2D": 1,
        "T_MINUS_3D": 1,
    }
    assert summary["matched_events"] == 1
    assert summary["market_snapshots"] == 5
    assert summary["checkpoint_gap_count"] == 2
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_checkpoint_capture_replay_marks_missing_requested_checkpoint() -> None:
    historical_database = FakeHistoricalDatabase()
    historical_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc(with_snapshots=True)])

    summary = run_checkpoint_capture(
        targets=[
            {
                "match_key": "match-legacy-checkpoint-gap",
                "source_match_id": 14689178,
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2025, 10, 8, 18, 0, tzinfo=UTC),
                "source_date": "2025-10-08",
            }
        ],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-odds-checkpoints.yml",
        dry_run=True,
        checkpoint_filter="T_MINUS_1D",
        legacy_backtest_database=historical_database,
    )

    assert summary["due_matches"] == 0
    assert summary["market_snapshots"] == 0
    assert summary["checkpoint_gap_count"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
