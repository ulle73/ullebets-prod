from datetime import UTC, datetime
from pathlib import Path
import json

from ullebets_v2.enrichment.service import run_match_enrichment_backfill_from_raw, run_match_enrichment_window
from ullebets_v2.enrichment.persistence import persist_enrichment_records
from ullebets_v2.enrichment.replay import (
    build_match_enrichment_documents,
    build_teamstats_source_rows,
    build_teamstats_source_rows_from_database,
)
from ullebets_v2.enrichment.reports import (
    build_match_enrichment_audit_rows,
    build_match_enrichment_parity_rows,
)
from ullebets_v2.support.schemas import build_support_documents


class FakeUpdateResult:
    def __init__(self, *, upserted: bool) -> None:
        self.upserted_id = "new" if upserted else None


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []

    def _matches(self, doc: dict, query: dict) -> bool:
        return all(doc.get(key) == value for key, value in query.items())

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> FakeUpdateResult:
        for doc in self.docs:
            if self._matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                return FakeUpdateResult(upserted=False)
        if not upsert:
            return FakeUpdateResult(upserted=False)
        new_doc = dict(query)
        new_doc.update(update.get("$set", {}))
        self.docs.append(new_doc)
        return FakeUpdateResult(upserted=True)

    def count_documents(self, query: dict | None = None) -> int:
        if not query:
            return len(self.docs)
        return sum(1 for doc in self.docs if self._matches(doc, query))


class FakeDatabase(dict):
    def __getitem__(self, collection_name: str) -> FakeCollection:
        if collection_name not in self:
            self[collection_name] = FakeCollection()
        return dict.__getitem__(self, collection_name)


class FakeReadCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        return list(self.docs)


class FakeReadDatabase(dict):
    def __getitem__(self, collection_name: str) -> FakeReadCollection:
        return dict.__getitem__(self, collection_name)


def build_support_docs() -> dict:
    return build_support_documents(
        leagues={
            "A-League Men": {
                "leagueId": 136,
                "categoryId": 34,
                "seasonId": 82603,
                "slug": "a-league-men",
                "teams": [
                    {"id": 2946, "name": "Adelaide United", "slug": "adelaide-united"},
                    {"id": 42210, "name": "Melbourne City", "slug": "melbourne-city"},
                ],
            }
        },
        league_urls={"A-League Men": "https://example.test/a-league-men"},
        ranking_rows=[],
        captured_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )


def build_match_record() -> dict:
    return {
        "matchId": 14671649,
        "timestamp": 1763714100,
        "date": "2025-11-21",
        "savedAt": "2025-11-22T05:14:52.532Z",
        "homeTeamId": 2946,
        "homeTeamName": "Adelaide United",
        "awayTeamId": 42210,
        "awayTeamName": "Melbourne City",
        "homeScore": 2,
        "awayScore": 1,
        "matchDetails": {
            "statistics": [
                {
                    "period": "ALL",
                    "groups": [
                        {
                            "groupName": "Match overview",
                            "statisticsItems": [
                                {"key": "totalShotsOnGoal", "homeValue": 11, "awayValue": 10},
                                {"key": "shotsOnGoal", "homeValue": 4, "awayValue": 3},
                                {"key": "cornerKicks", "homeValue": 6, "awayValue": 5},
                                {"key": "ballPossession", "homeValue": 31, "awayValue": 69},
                            ],
                        }
                    ],
                },
                {
                    "period": "1ST",
                    "groups": [
                        {
                            "groupName": "Match overview",
                            "statisticsItems": [
                                {"key": "totalShotsOnGoal", "homeValue": 6, "awayValue": 4},
                                {"key": "shotsOnGoal", "homeValue": 2, "awayValue": 1},
                                {"key": "cornerKicks", "homeValue": 3, "awayValue": 2},
                            ],
                        }
                    ],
                },
            ]
        },
        "incidents": {
            "incidents": [
                {"incidentType": "goal", "homeScore": 1, "awayScore": 0, "time": 5, "addedTime": 0},
                {"incidentType": "goal", "homeScore": 2, "awayScore": 0, "time": 50, "addedTime": 0},
                {"incidentType": "goal", "homeScore": 2, "awayScore": 1, "time": 70, "addedTime": 0},
            ]
        },
        "shotmap": {
            "shotmap": [
                {"isHome": True, "time": 10},
                {"isHome": False, "time": 55},
                {"isHome": True, "time": 72},
            ]
        },
    }


def write_teamstats_source(tmp_path: Path) -> Path:
    source_dir = tmp_path / "teamstats"
    source_dir.mkdir(parents=True, exist_ok=True)
    match = build_match_record()
    home_payload = {"full": [match]}
    away_payload = {"full": [match]}
    (source_dir / "adelaide_united_home_match_stats.json").write_text(
        json.dumps(home_payload),
        encoding="utf-8",
    )
    (source_dir / "melbourne_city_away_match_stats.json").write_text(
        json.dumps(away_payload),
        encoding="utf-8",
    )
    return source_dir


def build_mongo_teamstats_doc(*, source_file: str = "adelaide_united_home_match_stats.json") -> dict:
    return {
        "_importMeta": {
            "sourceFile": source_file,
            "teamRole": "home",
            "importedAt": "2026-05-17T11:00:00Z",
        },
        "full": [
            {
                **build_match_record(),
                "date": "2026-05-17",
                "savedAt": "2026-05-17T11:00:00Z",
            }
        ],
    }


def build_fixture_doc() -> dict:
    match = build_match_record()
    return {
        "match_key": "sofascore:14671649",
        "source_match_id": "14671649",
        "source_date": match["date"],
        "league_key": "a-league-men",
        "league_id": 136,
        "league_name": "A-League Men",
        "home_team_key": "a-league-men:adelaide-united",
        "away_team_key": "a-league-men:melbourne-city",
        "home_team_name": "Adelaide United",
        "away_team_name": "Melbourne City",
        "mapping_confidence": "exact_support_ids",
    }


def test_build_match_enrichment_documents_normalizes_stats_and_artifacts(tmp_path: Path) -> None:
    support_docs = build_support_docs()
    source_dir = write_teamstats_source(tmp_path)
    source_rows = build_teamstats_source_rows(source_dir)

    docs = build_match_enrichment_documents(
        source_rows=source_rows,
        support_docs=support_docs,
    )

    assert len(docs["raw_match_statistics"]) == 2
    assert len(docs["raw_incidents"]) == 2
    assert len(docs["raw_shotmaps"]) == 2
    assert len(docs["raw_results"]) == 2
    assert len(docs["fixtures_canonical"]) == 1

    total_shots_all = next(
        row
        for row in docs["match_stats_canonical"]
        if row["match_key"] == "sofascore:14671649"
        and row["stat_key"] == "totalShots"
        and row["period"] == "ALL"
        and row["scope"] == "all"
    )
    corners_home = next(
        row
        for row in docs["match_stats_canonical"]
        if row["stat_key"] == "cornerKicks"
        and row["period"] == "ALL"
        and row["scope"] == "home"
    )
    possession_total = [
        row
        for row in docs["match_stats_canonical"]
        if row["stat_key"] == "ballPossession"
        and row["scope"] == "all"
    ]

    assert total_shots_all["actual_value"] == 21
    assert corners_home["actual_value"] == 6
    assert possession_total == []
    assert docs["match_results"][0]["home_score"] == 2
    assert docs["match_results"][0]["away_score"] == 1
    assert docs["fixtures_canonical"][0]["match_key"] == "sofascore:14671649"
    assert docs["fixtures_canonical"][0]["start_time"] == datetime(2025, 11, 21, 8, 35, tzinfo=UTC)


def test_build_teamstats_source_rows_from_database_uses_import_meta() -> None:
    rows = build_teamstats_source_rows_from_database(
        FakeReadDatabase(
            {
                "teamstats": FakeReadCollection([build_mongo_teamstats_doc()]),
            }
        )
    )

    assert len(rows) == 1
    assert rows[0]["source_file"] == "adelaide_united_home_match_stats.json"
    assert rows[0]["source_role"] == "home"
    assert rows[0]["source_path"] == "mongodb:teamstats:adelaide_united_home_match_stats.json"
    assert rows[0]["matches"][0]["date"] == "2026-05-17"


def test_run_match_enrichment_window_falls_back_to_mongo_when_files_have_no_date(tmp_path: Path) -> None:
    support_docs = build_support_docs()
    source_dir = write_teamstats_source(tmp_path)
    legacy_teamstats_database = FakeReadDatabase(
        {
            "teamstats": FakeReadCollection([build_mongo_teamstats_doc()]),
        }
    )

    summary = run_match_enrichment_window(
        source_dir=source_dir,
        support_docs=support_docs,
        source_workflow="update-teamstats-and-teamprofiles.yml",
        dates=["2026-05-17"],
        legacy_teamstats_database=legacy_teamstats_database,
        dry_run=True,
    )

    assert summary["source_files"] == 1
    assert summary["raw_match_statistics"] == 1
    assert summary["match_results_canonical"] == 1
    assert summary["match_stats_canonical"] > 0
    assert summary["replay_source"] == "mongodb_fallback"
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}


def test_run_match_enrichment_backfill_from_raw_rebuilds_native_canonical_rows(tmp_path: Path) -> None:
    support_docs = build_support_docs()
    source_dir = write_teamstats_source(tmp_path)
    source_rows = build_teamstats_source_rows(source_dir)
    docs = build_match_enrichment_documents(
        source_rows=source_rows,
        support_docs=support_docs,
    )
    read_database = FakeReadDatabase(
        {
            "fixtures_canonical": FakeReadCollection([build_fixture_doc()]),
            "raw_match_statistics": FakeReadCollection(docs["raw_match_statistics"]),
            "raw_incidents": FakeReadCollection(docs["raw_incidents"]),
            "raw_shotmaps": FakeReadCollection(docs["raw_shotmaps"]),
            "raw_results": FakeReadCollection(docs["raw_results"]),
        }
    )

    summary = run_match_enrichment_backfill_from_raw(
        read_database=read_database,
        source_workflow="backfill-teamstats-from-date.yml",
        dates=["2025-11-21"],
        dry_run=True,
    )

    assert summary["replay_source"] == "v2_raw"
    assert summary["fixture_targets"] == 1
    assert summary["source_files"] == 0
    assert summary["raw_match_statistics"] == 2
    assert summary["match_results_canonical"] == 1
    assert summary["match_stats_canonical"] > 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["missing_fixture_context_matches"] == []


def test_match_enrichment_reports_and_persistence_are_rerun_safe(tmp_path: Path) -> None:
    support_docs = build_support_docs()
    source_dir = write_teamstats_source(tmp_path)
    source_rows = build_teamstats_source_rows(source_dir)
    docs = build_match_enrichment_documents(
        source_rows=source_rows,
        support_docs=support_docs,
    )

    parity_rows = build_match_enrichment_parity_rows(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        source_rows=source_rows,
        canonical_match_results=docs["match_results"],
    )
    audit_rows = build_match_enrichment_audit_rows(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        source_rows=source_rows,
        raw_match_statistics=docs["raw_match_statistics"],
        raw_incidents=docs["raw_incidents"],
        raw_shotmaps=docs["raw_shotmaps"],
        raw_results=docs["raw_results"],
        canonical_match_results=docs["match_results"],
        canonical_match_stats=docs["match_stats_canonical"],
    )

    assert parity_rows[0]["parity_status"] == "matched"
    assert parity_rows[0]["counts_old"]["distinct_match_count"] == 1
    assert parity_rows[0]["counts_v2"]["distinct_match_count"] == 1
    assert audit_rows[0]["metrics"]["match_stats_rows"] == len(docs["match_stats_canonical"])
    assert audit_rows[0]["metrics"]["missing_incidents"] == 0
    assert audit_rows[0]["metrics"]["missing_shotmap"] == 0
    assert audit_rows[0]["metrics"]["missing_scores"] == 0

    database = FakeDatabase()
    persist_enrichment_records(
        database,
        raw_match_statistics=docs["raw_match_statistics"],
        raw_incidents=docs["raw_incidents"],
        raw_shotmaps=docs["raw_shotmaps"],
        raw_results=docs["raw_results"],
        match_stats_canonical=docs["match_stats_canonical"],
        match_results=docs["match_results"],
        parity_rows=parity_rows,
        audit_rows=audit_rows,
    )
    persist_enrichment_records(
        database,
        raw_match_statistics=docs["raw_match_statistics"],
        raw_incidents=docs["raw_incidents"],
        raw_shotmaps=docs["raw_shotmaps"],
        raw_results=docs["raw_results"],
        match_stats_canonical=docs["match_stats_canonical"],
        match_results=docs["match_results"],
        parity_rows=parity_rows,
        audit_rows=audit_rows,
    )

    assert database["raw_match_statistics"].count_documents() == 2
    assert database["raw_incidents"].count_documents() == 2
    assert database["raw_shotmaps"].count_documents() == 2
    assert database["raw_results"].count_documents() == 2
    assert database["match_stats_canonical"].count_documents() == len(docs["match_stats_canonical"])
    assert database["match_results_canonical"].count_documents() == 1
    assert database["parity_reports"].count_documents() == 1
    assert database["audit_reports"].count_documents() == 1


def test_build_teamstats_source_rows_accepts_utf8_bom(tmp_path: Path) -> None:
    source_dir = tmp_path / "teamstats"
    source_dir.mkdir(parents=True, exist_ok=True)
    payload = {"full": [build_match_record()]}
    (source_dir / "adelaide_united_home_match_stats.json").write_text(
        json.dumps(payload),
        encoding="utf-8-sig",
    )

    rows = build_teamstats_source_rows(source_dir)

    assert len(rows) == 1
    assert rows[0]["source_role"] == "home"
    assert len(rows[0]["matches"]) == 1
