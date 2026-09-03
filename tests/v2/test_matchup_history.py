import pytest

from ullebets_v2.matchups import history


def test_history_rebuild_prioritizes_newest_dates_and_defers_bounded_backlog(monkeypatch) -> None:
    class Fixtures:
        def find(self, query, projection=None):
            return [{"match_key": query["fixture_date_stockholm"]}]

    class Scores:
        def find(self, query, projection=None):
            return []

    builds = []
    settlements = []

    def build(**kwargs):
        builds.append(kwargs["snapshot_date"])
        return {"entry_docs": []}

    def settle(**kwargs):
        settlements.append(kwargs)
        return {"resolved_rows": 0}

    monkeypatch.setattr(history, "run_matchups_score_build", build)
    monkeypatch.setattr(history, "run_matchups_league_avg_build", build)
    monkeypatch.setattr(history, "run_matchup_settlement", settle)

    summary = history.repair_matchup_history(
        database={
            "fixtures_canonical": Fixtures(),
            "matchups_score": Scores(),
            "matchups_league_avg": Scores(),
            "job_runs": Scores(),
        },
        date_from="2026-09-01",
        date_to="2026-09-03",
        source_workflow="enrich-matchups-results.yml",
        dry_run=True,
        max_rebuild_dates=2,
    )

    assert builds == ["2026-09-03", "2026-09-03", "2026-09-02", "2026-09-02"]
    assert summary["rebuilt_dates"] == 2
    assert summary["deferred_dates"] == 1
    assert summary["per_date"][0]["ranking_action"] == "deferred"
    assert all(row["unresolved_only"] is True for row in settlements)


@pytest.mark.parametrize("missing_collection", ["matchups_score", "matchups_league_avg"])
def test_history_repairs_missing_half_without_rebuilding_existing_rows(monkeypatch, missing_collection) -> None:
    from tests.v2.test_teamprofiles import FakeCollection, FakeDatabase

    day = "2026-08-30"
    existing = {"snapshot_date": day, "entry_key": "complete", "outcome_status": "resolved"}
    database = FakeDatabase({
        "fixtures_canonical": FakeCollection([{"fixture_date_stockholm": day}]),
        "matchups_score": FakeCollection([] if missing_collection == "matchups_score" else [existing]),
        "matchups_league_avg": FakeCollection([] if missing_collection == "matchups_league_avg" else [existing]),
    })
    builds = []
    for collection, function in (
        ("matchups_score", "run_matchups_score_build"),
        ("matchups_league_avg", "run_matchups_league_avg_build"),
    ):
        def build(*, _collection=collection, **kwargs):
            builds.append(_collection)
            return {"entry_docs": []}
        monkeypatch.setattr(history, function, build)
    monkeypatch.setattr(history, "run_matchup_settlement", lambda **kwargs: {"resolved_rows": 0})

    summary = history.repair_matchup_history(
        database=database, date_from=day, date_to=day,
        source_workflow="enrich-matchups-results.yml", dry_run=True, max_rebuild_dates=2,
    )

    assert builds == [missing_collection]
    assert summary["rebuilt_dates"] == 1
    assert summary["per_date"][0]["ranking_action"] == "rebuilt"


def test_history_rebuilds_a_snapshot_after_its_latest_build_failed(monkeypatch) -> None:
    from datetime import UTC, datetime
    from tests.v2.test_teamprofiles import FakeCollection, FakeDatabase

    day = "2026-08-30"
    existing = {"snapshot_date": day, "entry_key": "partial", "outcome_status": "pending_result"}

    class JobRuns(FakeCollection):
        def find(self, query=None, projection=None):
            return [
                {
                    "run_id": "old-success",
                    "job_name": "build_matchups_score",
                    "target_window": {"snapshot_date": day},
                    "status": "succeeded",
                    "started_at": datetime(2026, 9, 3, 15, 0, tzinfo=UTC),
                },
                {
                    "run_id": "latest-failure",
                    "job_name": "build_matchups_score",
                    "target_window": {"snapshot_date": day},
                    "status": "failed",
                    "started_at": datetime(2026, 9, 3, 16, 0, tzinfo=UTC),
                },
                {
                    "run_id": "league-success",
                    "job_name": "build_matchups_league_avg",
                    "target_window": {"snapshot_date": day},
                    "status": "succeeded",
                    "started_at": datetime(2026, 9, 3, 15, 0, tzinfo=UTC),
                },
            ]

    database = FakeDatabase({
        "fixtures_canonical": FakeCollection([{"fixture_date_stockholm": day}]),
        "matchups_score": FakeCollection([existing]),
        "matchups_league_avg": FakeCollection([existing]),
        "job_runs": JobRuns(),
    })
    builds = []
    monkeypatch.setattr(
        history, "run_matchups_score_build",
        lambda **kwargs: builds.append("matchups_score") or {"entry_docs": []},
    )
    monkeypatch.setattr(
        history, "run_matchups_league_avg_build",
        lambda **kwargs: builds.append("matchups_league_avg") or {"entry_docs": []},
    )
    monkeypatch.setattr(history, "run_matchup_settlement", lambda **kwargs: {"resolved_rows": 0})

    summary = history.repair_matchup_history(
        database=database, date_from=day, date_to=day,
        source_workflow="enrich-matchups-results.yml", dry_run=True, max_rebuild_dates=2,
    )

    assert builds == ["matchups_score"]
    assert summary["rebuilt_dates"] == 1
