from pathlib import Path

from ullebets_v2.historical_phase_a.service import run_historical_phase_a_backfill


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []

    def insert_one(self, doc: dict) -> None:
        self.docs.append(dict(doc))

    def update_one(self, query: dict, update: dict) -> None:
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                doc.update(update.get("$set", {}))
                return
        raise AssertionError(f"Missing document for query: {query}")


class FakeDatabase(dict):
    def __getitem__(self, collection_name: str) -> FakeCollection:
        if collection_name not in self:
            self[collection_name] = FakeCollection()
        return dict.__getitem__(self, collection_name)


def test_run_historical_phase_a_backfill_orchestrates_subjobs_and_tracks_parent_run(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_fixture_ingest(**kwargs):
        calls.append(("fixtures", kwargs))
        return {"job": "ingest_fixtures_window", "processed_dates": 2, "canonical_docs": 4}

    def fake_match_enrichment(**kwargs):
        calls.append(("enrichment", kwargs))
        return {"job": "ingest_match_enrichment", "match_results_canonical": 3, "match_stats_canonical": 12}

    def fake_verification(**kwargs):
        calls.append(("verification", kwargs))
        return {"job": "verify_match_enrichment", "audit_reports": 1, "health_reports": 1}

    def fake_teamprofiles(**kwargs):
        calls.append(("teamprofiles", kwargs))
        return {"job": "build_teamprofiles", "teamprofiles": 6}

    monkeypatch.setattr("ullebets_v2.historical_phase_a.service.run_fixture_ingest_window", fake_fixture_ingest)
    monkeypatch.setattr("ullebets_v2.historical_phase_a.service.run_match_enrichment_window", fake_match_enrichment)
    monkeypatch.setattr("ullebets_v2.historical_phase_a.service.run_match_enrichment_verification", fake_verification)
    monkeypatch.setattr("ullebets_v2.historical_phase_a.service.run_teamprofile_build", fake_teamprofiles)

    database = FakeDatabase()
    summary = run_historical_phase_a_backfill(
        dates=["2026-07-24", "2026-07-25"],
        support_docs={"teams": [], "leagues": []},
        old_payloads_by_date={"2026-07-24": {"matches": []}},
        fixture_source_dir=Path("legacy-fixtures"),
        teamstats_source_dir=Path("legacy-teamstats"),
        legacy_teamstats_database={"teamstats": []},
        database=database,
        dry_run=False,
    )

    assert [name for name, _ in calls] == ["fixtures", "enrichment", "verification", "teamprofiles"]
    assert calls[0][1]["mode"] == "replay"
    assert calls[0][1]["source_workflow"] == "import-fixtures-rolling.yml"
    assert calls[1][1]["source_workflow"] == "update-teamstats-and-teamprofiles.yml"
    assert calls[2][1]["source_workflow"] == "verify-teamstats-db.yml"
    assert calls[2][1]["from_date"] == "2026-07-24"
    assert calls[3][1]["source_workflow"] == "update-teamstats-and-teamprofiles.yml"
    assert calls[3][1]["profile_date"] == "2026-07-26"

    assert summary["job"] == "historical_phase_a_backfill"
    assert summary["dates"] == ["2026-07-24", "2026-07-25"]
    assert summary["verification_from_date"] == "2026-07-24"
    assert summary["profile_date"] == "2026-07-26"
    assert summary["steps_completed"] == ["fixtures", "enrichment", "verification", "teamprofiles"]

    run_doc = database["job_runs"].docs[0]
    assert run_doc["job_name"] == "historical_phase_a_backfill"
    assert run_doc["status"] == "succeeded"
    assert run_doc["target_window"] == {
        "dates": ["2026-07-24", "2026-07-25"],
        "from_date": "2026-07-24",
        "profile_date": "2026-07-26",
        "mode": "replay",
    }
    assert run_doc["metrics"]["steps_completed"] == 4
    assert run_doc["metrics"]["fixture_processed_dates"] == 2
    assert run_doc["metrics"]["teamprofiles"] == 6


def test_run_historical_phase_a_backfill_marks_parent_run_failed_on_subjob_error(monkeypatch) -> None:
    def fake_fixture_ingest(**kwargs):
        return {"job": "ingest_fixtures_window", "processed_dates": 1}

    def fake_match_enrichment(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("ullebets_v2.historical_phase_a.service.run_fixture_ingest_window", fake_fixture_ingest)
    monkeypatch.setattr("ullebets_v2.historical_phase_a.service.run_match_enrichment_window", fake_match_enrichment)

    database = FakeDatabase()

    try:
        run_historical_phase_a_backfill(
            dates=["2026-07-24"],
            support_docs={"teams": [], "leagues": []},
            old_payloads_by_date={},
            fixture_source_dir=Path("legacy-fixtures"),
            teamstats_source_dir=Path("legacy-teamstats"),
            legacy_teamstats_database=None,
            database=database,
            dry_run=False,
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Expected subjob failure to bubble up.")

    run_doc = database["job_runs"].docs[0]
    assert run_doc["status"] == "failed"
    assert run_doc["metrics"]["steps_completed"] == 1
    assert run_doc["error"] == {"type": "RuntimeError", "message": "boom"}
