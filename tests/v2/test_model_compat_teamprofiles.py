from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tests.v2.test_match_enrichment import build_support_docs
from tests.v2.test_teamprofiles import build_canonical_rows_with_raw
from ullebets_v2.model_compat import project_teamprofile_to_legacy_shape
from ullebets_v2.teamprofiles.service import run_teamprofile_build


def build_v2_profile(tmp_path: Path) -> dict:
    match_stats, match_results, raw_incidents, raw_shotmaps = build_canonical_rows_with_raw(tmp_path)
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=match_stats,
        match_results_canonical=match_results,
        raw_incidents=raw_incidents,
        raw_shotmaps=raw_shotmaps,
        profile_date="2025-12-01",
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )
    return summary["profile_docs"][0]


def test_project_teamprofile_to_legacy_shape_preserves_engine_fields(tmp_path: Path) -> None:
    projected = project_teamprofile_to_legacy_shape(build_v2_profile(tmp_path))

    assert sorted(projected.keys()) == [
        "behaviour",
        "games",
        "generatedAt",
        "leagueName",
        "meta",
        "specials",
        "statistics",
    ]
    assert projected["generatedAt"] == datetime(2026, 6, 22, 10, 0, tzinfo=UTC)
    assert projected["leagueName"] == "A-League Men"
    assert projected["meta"]["lagnamn"] == "Adelaide United"
    assert projected["meta"]["matchType"] == "home"
    assert projected["statistics"]["for"]["cornerKicks"]["ALL"]["value"] == 5.0
    assert projected["statistics"]["for"]["cornerKicks"]["ALL"]["rank"] == 1
    assert projected["statistics"]["for"]["cornerKicks"]["ALL"]["marketBias"] is None
    assert projected["statistics"]["leagueAverage"]["for"]["cornerKicks"]["ALL"]["value"] == 5.0
    assert "marketBias" not in projected["statistics"]["leagueAverage"]["for"]["cornerKicks"]["ALL"]


def test_project_teamprofile_to_legacy_shape_keeps_existing_period_fields(tmp_path: Path) -> None:
    profile_doc = build_v2_profile(tmp_path)
    profile_doc["statistics"]["for"]["cornerKicks"]["ALL"]["marketBias"] = {"lean": "over"}

    projected = project_teamprofile_to_legacy_shape(profile_doc)

    assert projected["statistics"]["for"]["cornerKicks"]["ALL"]["marketBias"] == {"lean": "over"}
    assert projected["statistics"]["for"]["cornerKicks"]["ALL"]["history"]
