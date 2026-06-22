from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ullebets_v2.closing.service import build_closing_line_docs, run_closing_capture

from tests.v2.test_odds_ingest import FakeOracle, build_support_docs, fake_transport


def test_build_closing_line_docs_keeps_latest_valid_prematch_snapshot() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)
    closing_docs = build_closing_line_docs(
        market_snapshot_docs=[
            {
                "snapshot_key": "snap-1",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "event_id": "evt-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "stat_key": "cornerKicks",
                "scope": "total",
                "period": "ALL",
                "line": 10.5,
                "over_odds": 1.9,
                "under_odds": 1.95,
                "snapshot_label": "T_MINUS_2D",
                "snapshot_time": now,
                "match_start_time": now + timedelta(days=2),
                "invalid_for_model": False,
            },
            {
                "snapshot_key": "snap-2",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "event_id": "evt-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "stat_key": "cornerKicks",
                "scope": "total",
                "period": "ALL",
                "line": 10.5,
                "over_odds": 1.8,
                "under_odds": 2.0,
                "snapshot_label": "T_MINUS_10M",
                "snapshot_time": now + timedelta(days=1, hours=23, minutes=50),
                "match_start_time": now + timedelta(days=2),
                "invalid_for_model": False,
            },
            {
                "snapshot_key": "snap-3",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "event_id": "evt-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "stat_key": "cornerKicks",
                "scope": "total",
                "period": "ALL",
                "line": 10.5,
                "over_odds": 1.7,
                "under_odds": 2.1,
                "snapshot_label": "POST_START",
                "snapshot_time": now + timedelta(days=2),
                "match_start_time": now + timedelta(days=2),
                "invalid_for_model": True,
            },
        ],
        refreshed_at=now,
    )

    assert len(closing_docs) == 1
    closing = closing_docs[0]
    assert closing["closing_key"] == "offer-1"
    assert closing["opening_over_odds"] == 1.9
    assert closing["closing_over_odds"] == 1.8
    assert closing["closing_snapshot_label"] == "T_MINUS_10M"
    assert closing["prematch_observation_count"] == 2
    assert closing["invalid_snapshot_count"] == 1


def test_run_closing_capture_dry_run_builds_closing_lines_for_due_window() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)

    def closing_transport(url: str, headers: dict[str, str], timeout_seconds: int):  # noqa: ARG001
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
                            "start": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
                            "group": "Premier League",
                        }
                    }
                ]
            },
        )

    summary = run_closing_capture(
        targets=[
            {
                "match_key": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": now + timedelta(minutes=10),
            }
        ],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-closing.yml",
        dry_run=True,
        transport=closing_transport,
        oracle=FakeOracle(),
        now=now,
    )

    assert summary["due_matches"] == 1
    assert summary["matched_events"] == 1
    assert summary["market_snapshots"] == 1
    assert summary["closing_lines"] == 1
    assert summary["invalid_for_model_rows"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_closing_capture_dry_run_handles_empty_window() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)
    summary = run_closing_capture(
        targets=[],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-closing.yml",
        dry_run=True,
        now=now,
    )

    assert summary["target_matches"] == 0
    assert summary["due_matches"] == 0
    assert summary["closing_lines"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
