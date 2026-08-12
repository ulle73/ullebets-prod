from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.clv_tracking.reports import build_clv_tracking_parity_rows
from ullebets_v2.clv_tracking.service import (
    build_legacy_reference_closing_line_docs,
    run_clv_tracking_refresh,
)


def test_run_clv_tracking_refresh_dry_run_tracks_direction_specific_closing_odds() -> None:
    summary = run_clv_tracking_refresh(
        tracked_bet_docs=[
            {
                "tracking_key": "sel-over",
                "selection_key": "sel-over",
                "prediction_key": "pred-over",
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
                "saved_odds": 2.0,
                "saved_at": "2026-06-22T09:50:00Z",
                "match_start_time": "2026-06-22T10:00:00Z",
                "invalid_for_model": False,
            },
            {
                "tracking_key": "sel-under",
                "selection_key": "sel-under",
                "prediction_key": "pred-under",
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
                "saved_odds": 1.9,
                "saved_at": "2026-06-22T09:50:00Z",
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
    assert over_doc["closing_quality"] == "t10"
    assert over_doc["official_clv"] is True
    assert over_doc["opening_odds"] is None
    assert over_doc["saved_odds"] == 2.0
    assert over_doc["clv_pct"] == 11.1
    assert over_doc["beat_closing_line"] is True
    assert under_doc["closing_odds"] == 2.0
    assert under_doc["clv_pct"] == -5.0
    assert under_doc["beat_closing_line"] is False
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_clv_tracking_keeps_t30_fallback_separate_from_official_clv() -> None:
    summary = run_clv_tracking_refresh(
        tracked_bet_docs=[
            {
                "tracking_key": "sel-over",
                "selection_key": "sel-over",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "saved_odds": 2.0,
                "odds_snapshot_time": "2026-06-22T08:00:00Z",
                "prediction_created_at": "2026-06-22T08:05:00Z",
                "match_start_time": "2026-06-22T10:00:00Z",
            }
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
                "closing_snapshot_time": "2026-06-22T09:30:00Z",
                "closing_snapshot_label": "T_MINUS_30M",
                "closing_quality": "t30_fallback",
                "closing_age_minutes": 30,
                "closing_over_odds": 1.8,
            }
        ],
        dry_run=True,
        refreshed_at=datetime(2026, 6, 22, 9, 31, tzinfo=UTC),
    )

    row = summary["clv_docs"][0]
    assert row["clv_status"] == "tracked_fallback_t30"
    assert row["clv_pct"] == 11.1
    assert row["closing_quality"] == "t30_fallback"
    assert row["official_clv"] is False
    assert summary["official_clv_rows"] == 0
    assert summary["fallback_clv_rows"] == 1


def test_run_clv_tracking_refresh_freezes_first_canonical_exposure() -> None:
    summary = run_clv_tracking_refresh(
        tracked_bet_docs=[
            {
                "tracking_key": "shared-selection",
                "selection_key": "shared-selection",
                "prediction_key": "pred-1",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 9.5,
                "saved_odds": 2.2,
                "saved_at": "2026-07-28T18:36:55Z",
                "match_start_time": "2026-07-30T00:30:00Z",
            },
            {
                "tracking_key": "shared-selection",
                "selection_key": "shared-selection",
                "prediction_key": "pred-2",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 9.5,
                "saved_odds": 2.3,
                "saved_at": "2026-07-28T18:41:26Z",
                "match_start_time": "2026-07-30T00:30:00Z",
            },
        ],
        closing_line_docs=[
            {
                "closing_key": "offer-1",
                "offer_key": "offer-1",
                "match_key": "match-1",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "total",
                "line": 9.5,
                "closing_snapshot_time": "2026-07-30T00:25:00Z",
                "closing_snapshot_label": "T_MINUS_10M",
                "closing_over_odds": 2.3,
                "prematch_observation_count": 2,
            }
        ],
        dry_run=True,
        refreshed_at=datetime(2026, 7, 30, 0, 26, tzinfo=UTC),
    )

    assert summary["clv_tracking_rows"] == 1
    assert summary["clv_docs"][0]["clv_key"] == "pred-1"
    assert summary["clv_docs"][0]["tracking_key"] == "shared-selection"
    assert summary["forward_exposure_audit"]["collapsed_duplicate_count"] == 1


def test_run_clv_tracking_refresh_dry_run_marks_missing_closing_and_invalid_timing() -> None:
    summary = run_clv_tracking_refresh(
        tracked_bet_docs=[
            {
                "tracking_key": "sel-missing",
                "selection_key": "sel-missing",
                "bet_key": "bet-missing",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "saved_odds": 2.0,
                "invalid_for_model": False,
            },
            {
                "tracking_key": "sel-invalid",
                "selection_key": "sel-invalid",
                "bet_key": "bet-invalid",
                "match_key": "match-2",
                "offer_key": "offer-2",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "home",
                "direction": "over",
                "line_value": 4.5,
                "saved_odds": 1.9,
                "invalid_for_model": True,
            },
        ],
        closing_line_docs=[],
        dry_run=True,
        refreshed_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["status_counts"] == {"invalid_snapshot_timing": 2}
    assert summary["parity_status_counts"] == {"mismatch": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}


def test_run_clv_tracking_rejects_snapshot_created_after_prediction() -> None:
    summary = run_clv_tracking_refresh(
        tracked_bet_docs=[
            {
                "prediction_key": "pred-invalid-timing",
                "tracking_key": "sel-invalid-timing",
                "selection_key": "sel-invalid-timing",
                "match_key": "match-1",
                "offer_key": "offer-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "away",
                "direction": "under",
                "line_value": 5.5,
                "saved_odds": 1.81,
                "odds_snapshot_time": "2026-07-30T00:25:00Z",
                "prediction_created_at": "2026-07-29T23:53:20Z",
                "match_start_time": "2026-07-30T00:30:00Z",
                "invalid_for_model": False,
                "valid_for_forward_evaluation": True,
            }
        ],
        closing_line_docs=[
            {
                "closing_key": "offer-1",
                "offer_key": "offer-1",
                "match_key": "match-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "away",
                "line": 5.5,
                "closing_snapshot_time": "2026-07-30T00:25:00Z",
                "closing_snapshot_label": "T_MINUS_10M",
                "closing_under_odds": 1.7,
            }
        ],
        dry_run=True,
        refreshed_at=datetime(2026, 7, 30, 3, 0, tzinfo=UTC),
    )

    assert summary["status_counts"] == {"invalid_snapshot_timing": 1}
    clv = summary["clv_docs"][0]
    assert clv["timing_status"] == "snapshot_after_prediction_creation"
    assert clv["saved_at"] == "2026-07-30T00:25:00Z"
    assert clv["prediction_created_at"] == "2026-07-29T23:53:20Z"
    assert clv["clv_pct"] is None
    assert clv["beat_closing_line"] is None


def test_run_clv_tracking_refresh_dry_run_handles_empty_input() -> None:
    summary = run_clv_tracking_refresh(
        tracked_bet_docs=[],
        closing_line_docs=[],
        dry_run=True,
    )

    assert summary["tracked_bets"] == 0
    assert summary["model_snapshots"] == 0
    assert summary["clv_tracking_rows"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_build_legacy_reference_closing_line_docs_groups_over_and_under_rows() -> None:
    docs = build_legacy_reference_closing_line_docs(
        [
            {
                "tracking_key": "sel-over",
                "match_key": "sofascore:1",
                "source_match_id": "1",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "opening_odds": 2.0,
                "opening_observed_at": "2026-06-22T09:00:00Z",
                "latest_observed_odds": 1.9,
                "latest_observed_at": "2026-06-22T09:50:00Z",
                "closing_odds": 1.8,
                "closing_observed_at": "2026-06-22T09:55:00Z",
                "prematch_observation_count": 3,
                "price_history": [
                    {"odds": 2.0, "observedAt": "2026-06-22T09:00:00Z"},
                    {"odds": 1.9, "observedAt": "2026-06-22T09:50:00Z"},
                    {"odds": 1.8, "observedAt": "2026-06-22T09:55:00Z"},
                ],
            },
            {
                "tracking_key": "sel-under",
                "match_key": "sofascore:1",
                "source_match_id": "1",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "under",
                "line_value": 10.5,
                "opening_odds": 1.9,
                "opening_observed_at": "2026-06-22T09:00:00Z",
                "latest_observed_odds": 2.0,
                "latest_observed_at": "2026-06-22T09:50:00Z",
                "closing_odds": 2.1,
                "closing_observed_at": "2026-06-22T09:55:00Z",
                "prematch_observation_count": 3,
                "price_history": [
                    {"odds": 1.9, "observedAt": "2026-06-22T09:00:00Z"},
                    {"odds": 2.0, "observedAt": "2026-06-22T09:50:00Z"},
                    {"odds": 2.1, "observedAt": "2026-06-22T09:55:00Z"},
                ],
            },
        ]
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc["opening_over_odds"] == 2.0
    assert doc["opening_under_odds"] == 1.9
    assert doc["closing_over_odds"] == 1.8
    assert doc["closing_under_odds"] == 2.1
    assert len(doc["price_history"]) == 3


def test_run_clv_tracking_refresh_dry_run_matches_legacy_shortlist_reference() -> None:
    legacy_reference_docs = [
        {
            "tracking_key": "1:Arsenal::Chelsea::cornerKicks::total::ALL::10.5::over::all::false",
            "match_key": "sofascore:1",
            "source_match_id": "1",
            "event_id": "evt-1",
            "event_url": "https://www.unibet.se/betting/sports/event/evt-1",
            "league_name": "Premier League",
            "home_team_name": "Arsenal",
            "away_team_name": "Chelsea",
            "stat_key": "cornerKicks",
            "period": "ALL",
            "scope": "total",
            "direction": "over",
            "line_value": 10.5,
            "saved_odds": 2.0,
            "opening_odds": 2.0,
            "opening_observed_at": "2026-06-22T09:00:00Z",
            "latest_observed_odds": 1.9,
            "latest_observed_at": "2026-06-22T09:50:00Z",
            "closing_odds": 1.8,
            "closing_observed_at": "2026-06-22T09:55:00Z",
            "clv_pct": 11.1,
            "implied_edge_delta": 5.56,
            "beat_closing_line": True,
            "prematch_observation_count": 3,
            "price_history": [
                {"odds": 2.0, "observedAt": "2026-06-22T09:00:00Z"},
                {"odds": 1.9, "observedAt": "2026-06-22T09:50:00Z"},
                {"odds": 1.8, "observedAt": "2026-06-22T09:55:00Z"},
            ],
            "legacy_status": "closed",
            "created_at": "2026-06-22T10:00:00Z",
        }
    ]
    summary = run_clv_tracking_refresh(
        tracked_bet_docs=[
            {
                "matchId": "1",
                "homeTeamName": "Arsenal",
                "awayTeamName": "Chelsea",
                "leagueName": "Premier League",
                "headline": "Över 10.5 Hörnor",
                "bet": {
                    "key": "Arsenal::Chelsea::cornerKicks::total::ALL::10.5::over::all::false",
                    "statKey": "cornerKicks",
                    "line": 10.5,
                    "direction": "over",
                    "scope": "total",
                    "period": "ALL",
                    "odds": 2.0,
                    "homeTeam": "Arsenal",
                    "awayTeam": "Chelsea",
                },
                "createdAt": "2026-06-22T09:00:00Z",
                "match_start_time": "2026-06-22T10:00:00Z",
                "trackingSource": "shortlist",
            }
        ],
        closing_line_docs=build_legacy_reference_closing_line_docs(legacy_reference_docs),
        legacy_clv_reference_docs=legacy_reference_docs,
        dry_run=True,
        refreshed_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    doc = summary["clv_docs"][0]
    assert doc["tracking_key"] == legacy_reference_docs[0]["tracking_key"]
    assert doc["clv_pct"] == 11.1
    assert doc["beat_closing_line"] is True


def test_build_clv_tracking_parity_rows_flags_legacy_metric_mismatches() -> None:
    parity_rows = build_clv_tracking_parity_rows(
        tracked_bet_docs=[{"tracking_key": "sel-1"}],
        clv_docs=[
            {
                "tracking_key": "sel-1",
                "saved_odds": 2.0,
                "opening_odds": 2.0,
                "latest_observed_odds": 1.8,
                "closing_odds": 1.8,
                "clv_pct": 11.1,
                "implied_edge_delta": 5.56,
                "beat_closing_line": True,
                "prematch_observation_count": 2,
                "clv_status": "tracked",
            }
        ],
        legacy_reference_docs=[
            {
                "tracking_key": "sel-1",
                "saved_odds": 2.0,
                "opening_odds": 2.0,
                "latest_observed_odds": 1.8,
                "closing_odds": 1.7,
                "clv_pct": 17.6,
                "implied_edge_delta": 8.82,
                "beat_closing_line": True,
                "prematch_observation_count": 2,
            }
        ],
        report_date="2026-06-22",
    )

    row = parity_rows[0]
    assert row["parity_status"] == "mismatch"
    assert row["counts_v2"]["legacy_comparable_count"] == 1
    assert row["counts_v2"]["legacy_closing_odds_mismatch_count"] == 1
    assert row["counts_v2"]["legacy_clv_pct_mismatch_count"] == 1
    assert row["counts_v2"]["legacy_implied_edge_delta_mismatch_count"] == 1
    assert "legacy_closing_odds_mismatches_present" in row["blocking_issues"]
