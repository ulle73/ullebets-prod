from datetime import UTC, datetime

from ullebets_v2.matchups.service import run_matchups_league_avg_build, run_matchups_score_build
from ullebets_v2.matchups_settlement.service import run_matchup_settlement
from ullebets_v2.teamprofiles.service import run_teamprofile_build

from tests.v2.test_match_enrichment import build_support_docs
from tests.v2.test_teamprofiles import build_canonical_rows
from tests.v2.test_matchups import build_target_match


def build_profiles() -> list[dict]:
    match_stats, match_results = build_canonical_rows()
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=match_stats,
        match_results_canonical=match_results,
        profile_date="2025-12-01",
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )
    return summary["profile_docs"]


def build_matchup_rows() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    match_stats, match_results = build_canonical_rows()
    target_match = build_target_match() | {
        "match_key": "sofascore:14671649",
        "source_match_id": "14671649",
        "source_date": "2025-11-21",
    }
    score_summary = run_matchups_score_build(
        source_workflow="dump-matchups.yml",
        target_matches=[target_match],
        snapshot_date="2025-12-05",
        teamprofile_docs=build_profiles(),
        dry_run=True,
    )
    league_summary = run_matchups_league_avg_build(
        source_workflow="dump-matchups.yml",
        target_matches=[target_match],
        snapshot_date="2025-12-05",
        teamprofile_docs=build_profiles(),
        dry_run=True,
    )
    return score_summary["entry_docs"], league_summary["entry_docs"], match_stats, match_results


def test_run_matchup_settlement_resolves_actuals_for_score_and_league_rows() -> None:
    score_rows, league_rows, match_stats, match_results = build_matchup_rows()
    summary = run_matchup_settlement(
        source_workflow="enrich-matchups-results.yml",
        date_from="2025-12-05",
        score_rows=score_rows,
        league_avg_rows=league_rows,
        match_stats_canonical=match_stats,
        match_results_canonical=match_results,
        dry_run=True,
        resolved_at=datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
    )

    assert summary["resolved_rows"] > 0
    assert summary["resolved_rows"] < len(score_rows) + len(league_rows)
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}

    score_row = next(
        row
        for row in summary["score_docs"]
        if row["stat_key"] == "cornerKicks" and row["period"] == "ALL" and row["scope"] == "total"
    )
    assert score_row["actual_value"] == 11
    assert score_row["home_value"] == 6
    assert score_row["away_value"] == 5
    assert score_row["outcome_status"] == "resolved"


def test_run_matchup_settlement_marks_missing_actuals() -> None:
    score_rows, league_rows, _, match_results = build_matchup_rows()
    summary = run_matchup_settlement(
        source_workflow="enrich-matchups-results.yml",
        date_from="2025-12-05",
        score_rows=score_rows,
        league_avg_rows=league_rows,
        match_stats_canonical=[],
        match_results_canonical=match_results,
        dry_run=True,
    )

    assert summary["resolved_rows"] == 0
    assert summary["parity_status_counts"] == {"mismatch": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}
    assert summary["outcome_status_counts"]["missing_actual"] == len(score_rows) + len(league_rows)


def test_run_matchup_settlement_handles_empty_window() -> None:
    summary = run_matchup_settlement(
        source_workflow="enrich-matchups-results.yml",
        date_from="2025-12-05",
        score_rows=[],
        league_avg_rows=[],
        match_stats_canonical=[],
        match_results_canonical=[],
        dry_run=True,
    )

    assert summary["resolved_rows"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
