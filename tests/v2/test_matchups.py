from datetime import UTC, datetime
from types import SimpleNamespace

import ullebets_v2.matchups.persistence as matchup_persistence
from ullebets_v2.matchups.service import _load_teamprofiles, run_matchups_league_avg_build, run_matchups_score_build
from ullebets_v2.matchups.service import build_matchups_score_docs
from ullebets_v2.matchups.persistence import persist_matchup_records
from ullebets_v2.teamprofiles.service import run_teamprofile_build

from tests.v2.test_teamprofiles import build_canonical_rows
from tests.v2.test_teamprofiles import FakeCollection, FakeDatabase
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
        "start_time": datetime(2025, 12, 5, 18, 0, tzinfo=UTC),
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
    assert {row["ranking_method"] for row in summary["entry_docs"]} == {"rolling_12_weighted_45d"}


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


def test_persist_matchups_replaces_stale_rows_for_the_same_snapshot_date() -> None:
    database = FakeDatabase(
        {
            "matchups_score": FakeCollection(
                [
                    {"entry_key": "active", "snapshot_date": "2026-08-17"},
                    {"entry_key": "stale", "snapshot_date": "2026-08-17"},
                    {"entry_key": "other-date", "snapshot_date": "2026-08-18"},
                ]
            )
        }
    )

    metrics = persist_matchup_records(
        database,
        collection_name="matchups_score",
        snapshot_date="2026-08-17",
        entry_docs=[{"entry_key": "active", "snapshot_date": "2026-08-17", "score": 55.0}],
        parity_rows=[],
        audit_rows=[],
        health_rows=[],
    )

    assert metrics["matchup_stale_deletes"] == 1
    assert {row["entry_key"] for row in database["matchups_score"].docs} == {"active", "other-date"}


def test_matchup_persistence_uses_bounded_bulk_writes_when_available(monkeypatch) -> None:
    class BulkCollection(FakeCollection):
        def __init__(self) -> None:
            super().__init__()
            self.batch_sizes: list[int] = []

        def bulk_write(self, operations, ordered: bool):
            assert ordered is False
            self.batch_sizes.append(len(operations))
            return SimpleNamespace(upserted_count=len(operations))

    collection = BulkCollection()
    monkeypatch.setattr(matchup_persistence, "UpdateOne", lambda query, update, upsert: (query, update, upsert))

    upserts = matchup_persistence._upsert_rows(
        collection,
        [{"entry_key": f"row-{index}"} for index in range(205)],
        ("entry_key",),
    )

    assert upserts == 205
    assert collection.batch_sizes == [100, 100, 5]


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


def test_dry_run_loads_profiles_without_persisting_records() -> None:
    database = FakeDatabase({"teamprofiles": FakeCollection(build_profiles())})

    summary = run_matchups_score_build(
        source_workflow="dump-matchups.yml",
        target_matches=[build_target_match()],
        snapshot_date="2025-12-05",
        database=database,
        dry_run=True,
    )

    assert summary["teamprofiles"] == len(build_profiles())
    assert summary["entries"] > 0
    assert database["matchups_score"].docs == []
    assert database["job_runs"].docs == []


def test_matchup_profile_load_includes_the_full_fixture_league() -> None:
    target = build_target_match()
    current_profiles = [
        {
            "team_key": target["home_team_key"],
            "league_key": target["league_key"],
            "match_type": "home",
            "profile_date": "current",
            "generated_at": datetime(2025, 12, 1, tzinfo=UTC),
        },
        {
            "team_key": target["away_team_key"],
            "league_key": target["league_key"],
            "match_type": "away",
            "profile_date": "current",
            "generated_at": datetime(2025, 12, 1, tzinfo=UTC),
        },
        {
            "team_key": "a-league-men:extra-team",
            "league_key": target["league_key"],
            "match_type": "home",
            "profile_date": "current",
            "generated_at": datetime(2025, 12, 1, tzinfo=UTC),
        },
    ]
    database = FakeDatabase({"teamprofiles": FakeCollection(current_profiles)})

    profiles = _load_teamprofiles(database, "2025-12-05", [target])

    assert {row["team_key"] for row in profiles} == {
        target["home_team_key"],
        target["away_team_key"],
        "a-league-men:extra-team",
    }


def test_market_bias_profiles_do_not_change_matchup_ranking() -> None:
    target = build_target_match()
    without_bias, _ = build_matchups_score_docs(
        target_matches=[target],
        teamprofile_docs=build_profiles(),
        snapshot_date="2025-12-05",
    )
    profiles = [
        {
            "team_key": target["home_team_key"],
            "league_key": target["league_key"],
            "venue_context": "home",
            "market_scope": "total",
            "stat_key": "totalShots",
            "period": "ALL",
            "as_of": datetime(2025, 12, 5, 17, 0, tzinfo=UTC),
            "direction": "over",
            "strength": "strong",
            "sample_size": 10,
            "non_push_sample_size": 10,
            "over_count": 7,
            "under_count": 3,
            "push_count": 0,
            "posterior_over_rate": 0.625,
            "shrunk_mean_residual": 1.4,
            "direction_confidence": 0.93,
            "method_version": "main_line_residual_v1",
        },
        {
            "team_key": target["away_team_key"],
            "league_key": target["league_key"],
            "venue_context": "away",
            "market_scope": "total",
            "stat_key": "totalShots",
            "period": "ALL",
            "as_of": datetime(2025, 12, 5, 17, 30, tzinfo=UTC),
            "direction": "under",
            "strength": "lean",
            "sample_size": 8,
            "non_push_sample_size": 7,
            "over_count": 3,
            "under_count": 4,
            "push_count": 1,
            "posterior_over_rate": 0.45,
            "shrunk_mean_residual": -0.8,
            "direction_confidence": 0.84,
            "method_version": "main_line_residual_v1",
        },
    ]
    with_bias, _ = build_matchups_score_docs(
        target_matches=[target],
        teamprofile_docs=build_profiles(),
        market_bias_profile_docs=profiles,
        snapshot_date="2025-12-05",
    )

    assert len(without_bias) == len(with_bias)
    for before, after in zip(without_bias, with_bias, strict=True):
        assert before["entry_key"] == after["entry_key"]
        assert before["score"] == after["score"]
        assert before["sort_key"] == after["sort_key"]
        assert before["rank_position"] == after["rank_position"]
    total = next(row for row in with_bias if row["stat_key"] == "totalShots" and row["period"] == "ALL" and row["scope"] == "total")
    assert [profile["team_key"] for profile in total["market_bias"]["profiles"]] == [target["home_team_key"], target["away_team_key"]]
