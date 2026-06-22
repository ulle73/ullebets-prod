from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.settlement.rules import settle_line
from ullebets_v2.settlement.service import run_model_snapshot_settlement


def test_settle_line_applies_win_loss_push_rules() -> None:
    over_win = settle_line(actual_value=8, line_value=7.5, direction="over", odds_decimal=1.9)
    under_loss = settle_line(actual_value=8, line_value=7.5, direction="under", odds_decimal=1.9)
    push = settle_line(actual_value=8, line_value=8, direction="over", odds_decimal=1.9)

    assert over_win["settlement_result"] == "win"
    assert over_win["roi_units"] == 0.9
    assert under_loss["settlement_result"] == "loss"
    assert under_loss["roi_units"] == -1.0
    assert push["settlement_result"] == "push"
    assert push["roi_units"] == 0.0


def test_run_model_snapshot_settlement_dry_run_settles_total_scope_against_all_scope_stats() -> None:
    summary = run_model_snapshot_settlement(
        source_workflow="correct-backtests-daily.yml",
        model_snapshot_docs=[
            {
                "selection_key": "sel-1",
                "match_key": "match-1",
                "bet_key": "bet-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "selected_odds": 1.95,
                "invalid_for_model": False,
            }
        ],
        match_stats_canonical=[
            {
                "match_key": "match-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "all",
                "actual_value": 12,
            }
        ],
        match_results_canonical=[
            {
                "match_key": "match-1",
                "home_score": 2,
                "away_score": 1,
            }
        ],
        dry_run=True,
        settled_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["settled_bets"] == 1
    assert summary["status_counts"] == {"settled": 1}
    assert summary["result_counts"] == {"win": 1}
    settled = summary["settled_docs"][0]
    assert settled["actual_value"] == 12
    assert settled["settlement_result"] == "win"
    assert settled["roi_units"] == 0.95
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_model_snapshot_settlement_dry_run_marks_pending_and_missing_actual() -> None:
    summary = run_model_snapshot_settlement(
        source_workflow="correct-backtests-daily.yml",
        model_snapshot_docs=[
            {
                "selection_key": "sel-1",
                "match_key": "match-1",
                "bet_key": "bet-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 10.5,
                "selected_odds": 1.95,
                "invalid_for_model": False,
            },
            {
                "selection_key": "sel-2",
                "match_key": "match-2",
                "bet_key": "bet-2",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "home",
                "direction": "over",
                "line_value": 4.5,
                "selected_odds": 2.1,
                "invalid_for_model": False,
            },
        ],
        match_stats_canonical=[],
        match_results_canonical=[
            {
                "match_key": "match-2",
                "home_score": 1,
                "away_score": 0,
            }
        ],
        dry_run=True,
        settled_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["status_counts"] == {"missing_actual": 1, "pending_result": 1}
    assert summary["parity_status_counts"] == {"mismatch": 1}
    assert summary["audit_status_counts"] == {"warn": 1}


def test_run_model_snapshot_settlement_dry_run_handles_empty_input() -> None:
    summary = run_model_snapshot_settlement(
        source_workflow="correct-backtests-daily.yml",
        model_snapshot_docs=[],
        match_stats_canonical=[],
        match_results_canonical=[],
        dry_run=True,
    )

    assert summary["model_snapshots"] == 0
    assert summary["settled_bets"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
