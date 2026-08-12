from datetime import UTC, datetime
from pathlib import Path
import json

from ullebets_v2.teamprofiles.persistence import persist_teamprofile_records
from ullebets_v2.enrichment.replay import build_match_enrichment_documents, build_teamstats_source_rows
from ullebets_v2.teamprofiles.service import (
    load_canonical_rows,
    run_teamprofile_build,
)

from tests.v2.test_match_enrichment import build_support_docs, build_match_record


class FakeUpdateResult:
    def __init__(self, *, upserted: bool) -> None:
        self.upserted_id = "new" if upserted else None


class FakeDeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = list(docs or [])
        self.find_queries: list[dict] = []
        self.update_queries: list[dict] = []

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, value in query.items():
            if isinstance(value, dict) and "$lt" in value:
                if doc.get(key) is None or doc[key] >= value["$lt"]:
                    return False
                continue
            if isinstance(value, dict) and "$in" in value:
                if doc.get(key) not in value["$in"]:
                    return False
                continue
            if isinstance(value, dict) and "$nin" in value:
                if doc.get(key) in value["$nin"]:
                    return False
                continue
            if doc.get(key) != value:
                return False
        return True

    def find(self, query: dict | None = None, projection: dict | None = None) -> list[dict]:
        del projection
        resolved_query = query or {}
        self.find_queries.append(resolved_query)
        return [dict(doc) for doc in self.docs if self._matches(doc, resolved_query)]

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> FakeUpdateResult:
        self.update_queries.append(dict(query))
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

    def delete_many(self, query: dict) -> FakeDeleteResult:
        remaining = [doc for doc in self.docs if not self._matches(doc, query)]
        deleted_count = len(self.docs) - len(remaining)
        self.docs = remaining
        return FakeDeleteResult(deleted_count)

    def count_documents(self, query: dict | None = None) -> int:
        if not query:
            return len(self.docs)
        return sum(1 for doc in self.docs if self._matches(doc, query))


class FakeDatabase(dict):
    def __getitem__(self, collection_name: str) -> FakeCollection:
        if collection_name not in self:
            self[collection_name] = FakeCollection()
        return dict.__getitem__(self, collection_name)


def test_load_canonical_rows_filters_results_in_database_and_batches_match_keys() -> None:
    profile_date = "2026-01-01"
    match_keys = [f"sofascore:{index}" for index in range(101)]
    database = FakeDatabase(
        {
            "match_results_canonical": FakeCollection(
                [
                    {"match_key": match_key, "source_date": "2025-12-31"}
                    for match_key in match_keys
                ]
                + [
                    {
                        "match_key": "sofascore:excluded",
                        "source_date": profile_date,
                    }
                ]
            ),
            "match_stats_canonical": FakeCollection(
                [{"match_key": match_key, "stat_key": "cornerKicks"} for match_key in match_keys]
            ),
            "raw_incidents": FakeCollection(
                [{"match_key": match_key, "payload": []} for match_key in match_keys]
            ),
            "raw_shotmaps": FakeCollection(
                [{"match_key": match_key, "payload": []} for match_key in match_keys]
            ),
        }
    )

    stats, results, incidents, shotmaps = load_canonical_rows(
        database,
        profile_date=profile_date,
    )

    assert len(results) == len(match_keys)
    assert len(stats) == len(match_keys)
    assert len(incidents) == len(match_keys)
    assert len(shotmaps) == len(match_keys)
    assert database["match_results_canonical"].find_queries == [
        {"source_date": {"$lt": profile_date}}
    ]
    for collection_name in (
        "match_stats_canonical",
        "raw_incidents",
        "raw_shotmaps",
    ):
        queries = database[collection_name].find_queries
        assert len(queries) == 3
        assert all(len(query["match_key"]["$in"]) <= 50 for query in queries)


def build_second_match() -> dict:
    match = build_match_record()
    match["matchId"] = 14671650
    match["date"] = "2025-11-28"
    match["savedAt"] = "2025-11-29T05:14:52.532Z"
    match["homeScore"] = 1
    match["awayScore"] = 2
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][0]["homeValue"] = 8
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][0]["awayValue"] = 14
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][1]["homeValue"] = 3
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][1]["awayValue"] = 6
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][2]["homeValue"] = 4
    match["matchDetails"]["statistics"][0]["groups"][0]["statisticsItems"][2]["awayValue"] = 8
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][0]["homeValue"] = 4
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][0]["awayValue"] = 6
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][1]["homeValue"] = 1
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][1]["awayValue"] = 2
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][2]["homeValue"] = 1
    match["matchDetails"]["statistics"][1]["groups"][0]["statisticsItems"][2]["awayValue"] = 4
    return match


def build_teamstats_dir(tmp_path: Path) -> Path:
    source_dir = tmp_path / "teamstats"
    source_dir.mkdir(parents=True, exist_ok=True)
    home_payload = {"full": [build_match_record(), build_second_match()]}
    (source_dir / "adelaide_united_home_match_stats.json").write_text(json.dumps(home_payload), encoding="utf-8")
    return source_dir


def build_canonical_rows_with_raw(tmp_path: Path) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    docs = build_match_enrichment_documents(
        source_rows=build_teamstats_source_rows(build_teamstats_dir(tmp_path)),
        support_docs=build_support_docs(),
    )
    return (
        docs["match_stats_canonical"],
        docs["match_results"],
        docs["raw_incidents"],
        docs["raw_shotmaps"],
    )


def build_canonical_rows() -> tuple[list[dict], list[dict]]:
    first = build_match_record()
    second = build_second_match()
    match_results = [
        {
            "match_key": "sofascore:14671649",
            "source_match_id": "14671649",
            "source_date": first["date"],
            "league_key": "a-league-men",
            "league_name": "A-League Men",
            "home_team_key": "a-league-men:2946",
            "away_team_key": "a-league-men:42210",
            "home_team_name": "Adelaide United",
            "away_team_name": "Melbourne City",
            "home_score": 2,
            "away_score": 1,
        },
        {
            "match_key": "sofascore:14671650",
            "source_match_id": "14671650",
            "source_date": second["date"],
            "league_key": "a-league-men",
            "league_name": "A-League Men",
            "home_team_key": "a-league-men:2946",
            "away_team_key": "a-league-men:42210",
            "home_team_name": "Adelaide United",
            "away_team_name": "Melbourne City",
            "home_score": 1,
            "away_score": 2,
        },
    ]
    match_stats = []
    for match_id, match in (("14671649", first), ("14671650", second)):
        for period_entry in match["matchDetails"]["statistics"]:
            period = period_entry["period"]
            for item in period_entry["groups"][0]["statisticsItems"]:
                stat_key = "totalShots" if item["key"] == "totalShotsOnGoal" else item["key"]
                match_stats.append(
                    {
                        "match_key": f"sofascore:{match_id}",
                        "source_match_id": match_id,
                        "source_date": match["date"],
                        "league_key": "a-league-men",
                        "home_team_key": "a-league-men:2946",
                        "away_team_key": "a-league-men:42210",
                        "stat_key": stat_key,
                        "period": period,
                        "scope": "home",
                        "actual_value": item["homeValue"],
                    }
                )
                match_stats.append(
                    {
                        "match_key": f"sofascore:{match_id}",
                        "source_match_id": match_id,
                        "source_date": match["date"],
                        "league_key": "a-league-men",
                        "home_team_key": "a-league-men:2946",
                        "away_team_key": "a-league-men:42210",
                        "stat_key": stat_key,
                        "period": period,
                        "scope": "away",
                        "actual_value": item["awayValue"],
                    }
                )
    return match_stats, match_results


def test_run_teamprofile_build_creates_ranked_profiles(tmp_path: Path) -> None:
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

    assert summary["teamprofiles"] == 2
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}

    home_profile = next(row for row in summary["profile_docs"] if row["team_key"] == "a-league-men:2946")
    away_profile = next(row for row in summary["profile_docs"] if row["team_key"] == "a-league-men:42210")
    assert home_profile["statistics"]["for"]["cornerKicks"]["ALL"]["value"] == 5.0
    assert away_profile["statistics"]["for"]["cornerKicks"]["ALL"]["value"] == 6.5
    assert home_profile["statistics"]["for"]["cornerKicks"]["ALL"]["rank"] == 1
    assert away_profile["statistics"]["for"]["cornerKicks"]["ALL"]["rank"] == 1
    assert summary["raw_incidents"] == 2
    assert summary["raw_shotmaps"] == 2
    assert round(home_profile["specials"]["shotsPerMinute"]["for"]["leading"], 6) == round(4 / 170, 6)
    assert round(home_profile["specials"]["shotsPerMinute"]["against"]["leading"], 6) == round(2 / 170, 6)
    assert home_profile["specials"]["firstGoal"]["scoreFirstPercentage"] == 1.0
    assert home_profile["specials"]["firstGoal"]["averageTimeScoredFirst"] == 5.0
    assert home_profile["specials"]["shotsPerTenMinutes"]["for"]["0-10"] == 1.0
    assert home_profile["specials"]["shotsPerTenMinutes"]["for"]["71-80"] == 1.0
    assert home_profile["specials"]["shotsPerTenMinutes"]["against"]["51-60"] == 1.0
    assert home_profile["specials"]["leagueAverage"]["firstGoal"]["scoreFirstPercentage"] == 1.0


def test_run_teamprofile_build_handles_empty_history() -> None:
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=[],
        match_results_canonical=[],
        raw_incidents=[],
        raw_shotmaps=[],
        dry_run=True,
    )

    assert summary["teamprofiles"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_teamprofile_build_accepts_missing_raw_artifacts_with_legacy_rows() -> None:
    match_stats, match_results = build_canonical_rows()
    summary = run_teamprofile_build(
        source_workflow="update-teamstats-and-teamprofiles.yml",
        support_docs=build_support_docs(),
        match_stats_canonical=match_stats,
        match_results_canonical=match_results,
        raw_incidents=[],
        raw_shotmaps=[],
        profile_date="2025-12-01",
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    profile = next(row for row in summary["profile_docs"] if row["team_key"] == "a-league-men:2946")
    assert profile["specials"]["firstGoal"]["scoreFirstPercentage"] is None
    assert profile["specials"]["shotsPerTenMinutes"]["for"]["0-10"] is None


def test_persist_teamprofile_records_replaces_stale_docs_for_same_profile_date() -> None:
    database = FakeDatabase(
        {
            "teamprofiles": FakeCollection(
                [
                    {"profile_key": "current|unknown:None|home", "profile_date": "current", "team_key": "unknown:None"},
                    {"profile_key": "2025-10-18|old-team|away", "profile_date": "2025-10-18", "team_key": "old-team"},
                    {"profile_key": "2025-10-17|keep-team|home", "profile_date": "2025-10-17", "team_key": "keep-team"},
                ]
            )
        }
    )

    metrics = persist_teamprofile_records(
        database,
        profile_docs=[
            {
                "profile_key": "current|team-a|home",
                "profile_date": "current",
                "team_key": "team-a",
                "match_type": "home",
            },
            {
                "profile_key": "current|team-b|away",
                "profile_date": "current",
                "team_key": "team-b",
                "match_type": "away",
            },
        ],
        parity_rows=[],
        audit_rows=[],
        health_rows=[],
        replace_profile_date="current",
    )

    assert metrics["teamprofile_deleted"] == 1
    assert database["teamprofiles"].count_documents({"profile_date": "current"}) == 2
    assert database["teamprofiles"].count_documents({"profile_key": "current|unknown:None|home"}) == 0
    assert database["teamprofiles"].count_documents({"profile_key": "2025-10-18|old-team|away"}) == 1
    assert database["teamprofiles"].count_documents({"profile_key": "2025-10-17|keep-team|home"}) == 1
    assert database["teamprofiles"].update_queries == [
        {
            "team_key": "team-a",
            "profile_date": "current",
            "match_type": "home",
        },
        {
            "team_key": "team-b",
            "profile_date": "current",
            "match_type": "away",
        },
    ]
