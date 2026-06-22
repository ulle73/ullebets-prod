from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.clv_tracking.service import run_clv_tracking_refresh


def test_run_clv_tracking_refresh_dry_run_tracks_direction_specific_closing_odds() -> None:
    summary = run_clv_tracking_refresh(
        model_snapshot_docs=[
            {
                "selection_key": "sel-over",
                "bet_key": "bet-over",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "event_id": "evt-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "selected_odds": 2.0,
                "snapshot_time": "2026-06-22T09:50:00Z",
                "match_start_time": "2026-06-22T10:00:00Z",
                "invalid_for_model": False,
            },
            {
                "selection_key": "sel-under",
                "bet_key": "bet-under",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "event_id": "evt-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "under",
                "line_value": 10.5,
                "selected_odds": 1.9,
                "snapshot_time": "2026-06-22T09:50:00Z",
                "match_start_time": "2026-06-22T10:00:00Z",
                "invalid_for_model": False,
            },
        ],
        closing_line_docs=[
            {
                "closing_key": "offer-1",
                "offer_key": "offer-1",
                "match_key": "match-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line": 10.5,
                "closing_snapshot_time": "2026-06-22T09:55:00Z",
                "closing_snapshot_label": "T_MINUS_10M",
                "closing_over_odds": 1.8,
                "closing_under_odds": 2.0,
                "prematch_observation_count": 2,
            }
        ],
        dry_run=True,
        refreshed_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["clv_tracking_rows"] == 2
    assert summary["status_counts"] == {"tracked": 2}
    over_doc = next(row for row in summary["clv_docs"] if row["tracking_key"] == "sel-over")
    under_doc = next(row for row in summary["clv_docs"] if row["tracking_key"] == "sel-under")
    assert over_doc["closing_odds"] == 1.8
    assert over_doc["clv_pct"] == 11.1
    assert over_doc["beat_closing_line"] is True
    assert under_doc["closing_odds"] == 2.0
    assert under_doc["clv_pct"] == -5.0
    assert under_doc["beat_closing_line"] is False
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_clv_tracking_refresh_dry_run_marks_missing_closing_and_invalid_timing() -> None:
    summary = run_clv_tracking_refresh(
        model_snapshot_docs=[
            {
                "selection_key": "sel-missing",
                "bet_key": "bet-missing",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "selected_odds": 2.0,
                "invalid_for_model": False,
            },
            {
                "selection_key": "sel-invalid",
                "bet_key": "bet-invalid",
                "match_key": "match-2",
                "offer_key": "offer-2",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "home",
                "direction": "over",
                "line_value": 4.5,
                "selected_odds": 1.9,
                "invalid_for_model": True,
            },
        ],
        closing_line_docs=[],
        dry_run=True,
        refreshed_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["status_counts"] == {"invalid_snapshot_timing": 1, "missing_closing_line": 1}
    assert summary["parity_status_counts"] == {"mismatch": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}


def test_run_clv_tracking_refresh_dry_run_handles_empty_input() -> None:
    summary = run_clv_tracking_refresh(
        model_snapshot_docs=[],
        closing_line_docs=[],
        dry_run=True,
    )

    assert summary["model_snapshots"] == 0
    assert summary["clv_tracking_rows"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
