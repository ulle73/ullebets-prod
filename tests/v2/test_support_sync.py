from datetime import UTC, datetime

from ullebets_v2.support.loaders import LoadedSupportSource
from ullebets_v2.support.opta import merge_opta_fields
from ullebets_v2.support.persistence import persist_support_records
from ullebets_v2.support.reports import (
    build_support_audit_rows,
    build_support_health_rows,
    build_support_parity_rows,
)
from ullebets_v2.support.schemas import build_support_documents, build_support_source_docs
from ullebets_v2.support.service import run_support_sync


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
                doc.update(update.get("$set", {}))
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


def build_fixture_support_inputs() -> tuple[dict, dict, list[dict], list[dict], list[LoadedSupportSource]]:
    leagues = {
        "Premier League": {
            "leagueId": 17,
            "country": "England",
            "categoryId": 1,
            "seasonId": 61627,
            "groupId": 1001,
            "slug": "premier-league",
            "teams": [
                {
                    "id": 100,
                    "name": "Arsenal",
                    "slug": "arsenal",
                    "imageUrl": "/images/teams/100.png",
                    "optaId": 3,
                    "optaRank": 1,
                    "optaRating": 99.0,
                },
                {
                    "id": 101,
                    "name": "Bournemouth",
                    "slug": "bournemouth",
                    "imageUrl": "/images/teams/101.png",
                    "optaId": None,
                    "optaRank": None,
                    "optaRating": None,
                },
            ],
        }
    }
    league_urls = {
        "Premier League": {
            "countrySlug": "england",
            "leagueSlug": "premier_league",
            "baseUrl": "https://example.test/premier-league.json",
            "lookupSlugs": ["premier league"],
        }
    }
    opta_rows = [
        {"optaId": 3, "rank": 1, "currentRating": 100.0, "contestantName": "Arsenal"},
        {
            "optaId": 91,
            "rank": 14,
            "currentRating": 92.1,
            "contestantName": "AFC Bournemouth",
            "contestantShortName": "Bournemouth",
        },
    ]
    ranking_rows = [
        {
            "league": "Premier League",
            "leagueAvgOptaRating": 92.7,
            "ranking": {"cornerKicks": {"leagueAverage": {"ALL": {"overall": 9.9}}}},
        }
    ]
    source_inputs = [
        LoadedSupportSource("leagues-and-teams", "file", "C:/tmp/leagues-and-teams.json", leagues),
        LoadedSupportSource("unibet-league-urls", "file", "C:/tmp/unibetLeagueUrls.json", league_urls),
        LoadedSupportSource("opta-power-rankings", "url", "https://example.test/opta.json", opta_rows),
        LoadedSupportSource("league-ranking", "url", "https://example.test/league_ranking.json", ranking_rows),
    ]
    return leagues, league_urls, opta_rows, ranking_rows, source_inputs


def test_build_support_documents_creates_canonical_support_rows() -> None:
    leagues, league_urls, opta_rows, ranking_rows, _ = build_fixture_support_inputs()

    docs = build_support_documents(
        leagues,
        league_urls,
        ranking_rows,
        opta_rows=opta_rows,
        captured_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )

    assert docs["source"]["source_type"] == "support_sync"
    assert docs["source"]["league_count"] == 1
    assert docs["leagues"][0]["league_key"] == "premier-league"
    assert docs["leagues"][0]["unibet_base_url"] == "https://example.test/premier-league.json"
    assert docs["leagues"][0]["unibet_lookup_slugs"] == ["premier league"]
    assert docs["teams"][0]["team_key"] == "premier-league:100"
    assert docs["teams"][1]["opta_id"] == 91
    assert docs["teams"][1]["opta_match_method"] == "name_override"
    assert docs["rankings"][0]["league_key"] == "premier-league"
    assert docs["rankings"][0]["matched_support_league"] is True


def test_merge_opta_fields_updates_matching_team_by_id_and_override() -> None:
    teams = [
        {
            "team_key": "premier-league:100",
            "team_name": "Arsenal",
            "opta_id": 3,
            "opta_rank": None,
            "opta_rating": None,
        },
        {
            "team_key": "premier-league:101",
            "team_name": "Bournemouth",
            "opta_id": None,
            "opta_rank": None,
            "opta_rating": None,
        },
    ]
    opta_rows = [
        {"optaId": 3, "rank": 1, "currentRating": 100.0, "contestantName": "Arsenal"},
        {
            "optaId": 91,
            "rank": 14,
            "currentRating": 92.1,
            "contestantName": "AFC Bournemouth",
            "contestantShortName": "Bournemouth",
        },
    ]

    merged = merge_opta_fields(teams, opta_rows)

    assert merged[0]["opta_rank"] == 1
    assert merged[0]["opta_rating"] == 100.0
    assert merged[0]["opta_match_method"] == "opta_id"
    assert merged[1]["opta_id"] == 91
    assert merged[1]["opta_match_method"] == "name_override"


def test_support_reports_and_persistence_are_rerun_safe() -> None:
    leagues, league_urls, opta_rows, ranking_rows, source_inputs = build_fixture_support_inputs()
    old_docs = build_support_documents(leagues, league_urls, [])
    v2_docs = build_support_documents(leagues, league_urls, ranking_rows, opta_rows=opta_rows)
    source_docs = build_support_source_docs(
        source_payloads=[
            {
                "source_name": source.source_name,
                "source_kind": source.source_kind,
                "source_locator": source.source_locator,
                "payload": source.payload,
            }
            for source in source_inputs
        ]
    )
    parity_rows = build_support_parity_rows(
        source_workflow="update-opta.yml",
        old_support_docs=old_docs,
        v2_support_docs=v2_docs,
    )
    audit_rows = build_support_audit_rows(
        source_workflow="update-opta.yml",
        source_inputs=source_inputs,
        support_docs=v2_docs,
    )
    health_rows = build_support_health_rows(
        source_workflow="update-opta.yml",
        source_inputs=source_inputs,
        support_docs=v2_docs,
    )

    assert parity_rows[0]["parity_status"] == "matched"
    assert audit_rows[0]["status"] == "ok"
    assert health_rows[0]["status"] == "ok"

    database = FakeDatabase()
    persist_support_records(
        database,
        source_docs=source_docs,
        support_docs=v2_docs,
        parity_rows=parity_rows,
        audit_rows=audit_rows,
        health_rows=health_rows,
    )
    persist_support_records(
        database,
        source_docs=source_docs,
        support_docs=v2_docs,
        parity_rows=parity_rows,
        audit_rows=audit_rows,
        health_rows=health_rows,
    )

    assert database["support_sources"].count_documents() == 4
    assert database["support_leagues"].count_documents() == 1
    assert database["support_teams"].count_documents() == 2
    assert database["support_rankings"].count_documents() == 1
    assert database["parity_reports"].count_documents() == 1
    assert database["audit_reports"].count_documents() == 1
    assert database["health_reports"].count_documents() == 1


def test_run_support_sync_dry_run_summarizes_successful_sync() -> None:
    leagues, league_urls, opta_rows, ranking_rows, source_inputs = build_fixture_support_inputs()

    summary = run_support_sync(
        source_workflow="update-opta.yml",
        leagues_payload=leagues,
        league_urls_payload=league_urls,
        source_inputs=source_inputs,
        opta_payload=opta_rows,
        league_ranking_payload=ranking_rows,
        dry_run=True,
        captured_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )

    assert summary["support_sources"] == 4
    assert summary["support_leagues"] == 1
    assert summary["support_teams"] == 2
    assert summary["support_rankings"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
