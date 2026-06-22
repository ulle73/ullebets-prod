from datetime import UTC, datetime

from ullebets_v2.matchups.service import run_matchups_league_avg_build, run_matchups_score_build
from ullebets_v2.teamprofiles.service import run_teamprofile_build

from tests.v2.test_teamprofiles import build_canonical_rows
from tests.v2.test_match_enrichment import build_support_docs


def build_target_match() -> dict:
    return {
        "match_key": "sofascore:future-1",
        "source_match_id": "future-1",
        "source_date": "2025-12-05",
        "league_key": "a-league-men",
        "league_id": 136,
        "league_name": "A-League Men",
        "home_team_key": "a-league-men:2946",
        "away_team_key": "a-league-men:42210",
        "home_team_name": "Adelaide United",
        "away_team_name": "Melbourne City",
    }


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


def test_run_matchups_score_build_creates_ranked_entries() -> None:
    summary = run_matchups_score_build(
        source_workflow="dump-matchups.yml",
        target_matches=[build_target_match()],
        snapshot_date="2025-12-05",
        teamprofile_docs=build_profiles(),
        dry_run=True,
    )

    assert summary["entries"] > 0
    assert summary["missing_profile_matches"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    assert any(row["is_top_50"] for row in summary["entry_docs"])


def test_run_matchups_league_avg_build_creates_ratio_entries() -> None:
    summary = run_matchups_league_avg_build(
        source_workflow="dump-matchups.yml",
        target_matches=[build_target_match()],
        snapshot_date="2025-12-05",
        teamprofile_docs=build_profiles(),
        dry_run=True,
    )

    assert summary["entries"] > 0
    assert summary["missing_profile_matches"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    assert any(row["condition"] == "ratio" for row in summary["entry_docs"])


def test_run_matchups_builds_no_targets_on_empty_window() -> None:
    summary = run_matchups_score_build(
        source_workflow="dump-matchups.yml",
        target_matches=[],
        snapshot_date="2025-12-05",
        teamprofile_docs=build_profiles(),
        dry_run=True,
    )

    assert summary["entries"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
