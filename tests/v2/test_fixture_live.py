from datetime import UTC, datetime
from pathlib import Path

from ullebets_v2.fixtures.live import (
    FixtureSourceConfig,
    HttpJsonResponse,
    build_aggregated_fixture_payload,
    build_category_plan,
    fetch_live_fixture_batches,
)
from ullebets_v2.fixtures.service import run_fixture_ingest_window
from ullebets_v2.fixtures.persistence import persist_fixture_records
from ullebets_v2.fixtures.reports import (
    build_fixture_audit_rows,
    build_fixture_parity_rows,
    build_source_link_documents,
)
from ullebets_v2.fixtures.replay import build_fixture_documents
from ullebets_v2.parity.reports import build_parity_report_row
from ullebets_v2.storage.indexes import build_core_index_plan
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

    def insert_one(self, doc: dict) -> None:
        self.docs.append(dict(doc))

    def count_documents(self, query: dict | None = None) -> int:
        if not query:
            return len(self.docs)
        return sum(1 for doc in self.docs if self._matches(doc, query))


class FakeDatabase(dict):
    def __getitem__(self, collection_name: str) -> FakeCollection:
        if collection_name not in self:
            self[collection_name] = FakeCollection()
        return dict.__getitem__(self, collection_name)


def build_support_docs() -> dict:
    return build_support_documents(
        leagues={
            "Brasileirão Série A": {
                "leagueId": 325,
                "categoryId": 13,
                "seasonId": 72034,
                "slug": "brasileirao-serie-a",
                "teams": [
                    {"id": 1977, "name": "Atlético Mineiro", "slug": "atletico-mineiro"},
                    {"id": 1959, "name": "Sport Recife", "slug": "sport-recife"},
                ],
            }
        },
        league_urls={"Brasileirão Série A": "https://example.test/brasileirao"},
        ranking_rows=[],
        captured_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )


def build_old_fixture_payload() -> dict:
    return {
        "date": "2025-10-08",
        "savedAt": "2025-10-08T19:53:08.599Z",
        "matches": [
            {
                "id": 14689178,
                "startTimestamp": 1759960800,
                "slug": "atletico-mineiro-sport-recife",
                "status": {"type": "notstarted"},
                "season": {"id": 72034},
                "tournament": {
                    "id": 83,
                    "name": "Brasileirão Betano",
                    "slug": "brasileirao-serie-a",
                    "category": {"id": 13, "name": "Brazil"},
                    "uniqueTournament": {
                        "id": 325,
                        "name": "Brasileirão Betano",
                        "slug": "brasileirao-serie-a",
                    },
                },
                "homeTeam": {"id": 1977, "name": "Atlético Mineiro", "slug": "atletico-mineiro"},
                "awayTeam": {"id": 1959, "name": "Sport Recife", "slug": "sport-recife"},
            }
        ],
    }


def test_index_plan_contains_fixture_source_links() -> None:
    plan = build_core_index_plan()
    names = {item["collection"] for item in plan}
    assert "fixture_source_links" in names


def test_build_category_plan_groups_leagues_by_category() -> None:
    plan = build_category_plan(build_support_docs())
    assert plan == [{"category_id": 13, "league_ids": [325]}]


def test_fixture_source_config_uses_default_base_urls_when_env_is_sparse() -> None:
    config = FixtureSourceConfig.from_env({})

    assert config.rapidapi_keys == []
    assert config.rapidapi_sportapi7_base_url == "https://sportapi7.p.rapidapi.com"
    assert config.rapidapi_sofascore_base_url == "https://sofascore.p.rapidapi.com"
    assert config.rapidapi_sport_api_real_time_base_url == "https://sport-api-real-time.p.rapidapi.com"
    assert config.rapidapi_sofascore_sport_api_base_url == "https://sofascore-sport-api.p.rapidapi.com"
    assert config.sofascore_public_api_base_url == "https://api.sofascore.com/api/v1"


def test_fetch_live_fixture_batches_records_endpoint_metadata() -> None:
    def transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:
        assert headers["x-rapidapi-key"] == "key-1"
        if "sportapi7" in url:
            return HttpJsonResponse(status=404, headers={}, data={})
        return HttpJsonResponse(
            status=200,
            headers={"content-type": "application/json"},
            data={"events": build_old_fixture_payload()["matches"]},
        )

    batches = fetch_live_fixture_batches(
        date="2025-10-08",
        support_docs=build_support_docs(),
        source_config=FixtureSourceConfig(
            rapidapi_keys=["key-1"],
            rapidapi_sportapi7_base_url="https://sportapi7.example.test",
            rapidapi_sofascore_base_url="https://sofascore.example.test",
            rapidapi_sport_api_real_time_base_url="https://realtime.example.test",
            rapidapi_sofascore_sport_api_base_url="https://sportapi.example.test",
            sofascore_public_api_base_url="https://public.example.test",
        ),
        transport=transport,
        fetched_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )

    assert len(batches) == 1
    assert batches[0]["source_name"] == "sofascore-api-dojo-tournaments"
    assert batches[0]["source_provider"] == "rapidapi"
    assert batches[0]["source_date"] == "2025-10-08"
    assert batches[0]["category_id"] == 13
    assert batches[0]["event_count"] == 1
    assert "categoryId=13" in batches[0]["source_url"]


def test_live_fixture_reports_and_persistence_are_rerun_safe() -> None:
    support_docs = build_support_docs()
    old_payload = build_old_fixture_payload()
    fetched_at = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    live_batch = {
        "payload_hash": "raw-live-1",
        "source_name": "sofascore-api-dojo-tournaments",
        "source_provider": "rapidapi",
        "source_date": "2025-10-08",
        "source_url": "https://sofascore.example.test/tournaments/get-scheduled-events?categoryId=13&date=2025-10-08",
        "category_id": 13,
        "fetched_at": fetched_at,
        "api_key_slot": 0,
        "events": old_payload["matches"],
        "event_count": 1,
        "payload": {"events": old_payload["matches"]},
    }
    docs = build_fixture_documents(
        payload=old_payload,
        support_docs=support_docs,
        source_path=Path(r"C:\dev\frontend\ullebets-vecel\matches-for-date\fixtures-2025-10-08.json"),
    )
    source_links = build_source_link_documents(
        raw_fixture_docs=[live_batch],
        canonical_fixture_docs=docs["canonical"],
    )
    parity_rows = build_fixture_parity_rows(
        old_workflow="import-fixtures-rolling.yml",
        old_payloads_by_date={"2025-10-08": old_payload},
        canonical_fixture_docs=docs["canonical"],
        source_link_docs=source_links,
    )
    audit_rows = build_fixture_audit_rows(
        source_workflow="import-fixtures-rolling.yml",
        raw_fixture_docs=[live_batch],
        canonical_fixture_docs=docs["canonical"],
        source_link_docs=source_links,
        old_payloads_by_date={"2025-10-08": old_payload},
    )

    assert source_links[0]["match_key"] == "sofascore:14689178"
    assert parity_rows[0]["parity_status"] == "matched"
    assert parity_rows[0]["counts_old"]["match_count"] == 1
    assert parity_rows[0]["counts_v2"]["match_count"] == 1
    assert audit_rows[0]["metrics"]["unmatched_count"] == 0

    database = FakeDatabase()
    persist_fixture_records(
        database,
        raw_fixture_docs=[live_batch],
        canonical_fixture_docs=docs["canonical"],
        source_link_docs=source_links,
        parity_rows=parity_rows,
        audit_rows=audit_rows,
    )
    persist_fixture_records(
        database,
        raw_fixture_docs=[live_batch],
        canonical_fixture_docs=docs["canonical"],
        source_link_docs=source_links,
        parity_rows=parity_rows,
        audit_rows=audit_rows,
    )

    assert database["raw_fixtures"].count_documents() == 1
    assert database["fixtures_canonical"].count_documents() == 1
    assert database["fixture_source_links"].count_documents() == 1
    assert database["parity_reports"].count_documents() == 1
    assert database["audit_reports"].count_documents() == 1


def test_build_aggregated_fixture_payload_dedupes_event_ids() -> None:
    old_payload = build_old_fixture_payload()
    fetched_at = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    payload = build_aggregated_fixture_payload(
        date="2025-10-08",
        live_batches=[
            {
                "source_name": "source-a",
                "source_provider": "rapidapi",
                "source_url": "https://source-a.test",
                "category_id": 13,
                "api_key_slot": 0,
                "events": old_payload["matches"],
            },
            {
                "source_name": "source-b",
                "source_provider": "sofascore",
                "source_url": "https://source-b.test",
                "category_id": 13,
                "api_key_slot": None,
                "events": old_payload["matches"],
            },
        ],
        fetched_at=fetched_at,
    )

    assert payload["date"] == "2025-10-08"
    assert len(payload["matches"]) == 1
    assert payload["sources"][0]["source_name"] == "source-a"
    assert payload["sources"][1]["source_name"] == "source-b"


def test_run_fixture_ingest_window_live_writes_job_and_reports() -> None:
    support_docs = build_support_docs()
    old_payload = build_old_fixture_payload()
    database = FakeDatabase()

    def transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:
        if "sportapi7" in url:
            return HttpJsonResponse(status=404, headers={}, data={})
        return HttpJsonResponse(
            status=200,
            headers={"content-type": "application/json"},
            data={"events": old_payload["matches"]},
        )

    summary = run_fixture_ingest_window(
        mode="live",
        dates=["2025-10-08"],
        support_docs=support_docs,
        source_workflow="import-fixtures-rolling.yml",
        old_payloads_by_date={"2025-10-08": old_payload},
        database=database,
        dry_run=False,
        source_config=FixtureSourceConfig(
            rapidapi_keys=["key-1"],
            rapidapi_sportapi7_base_url="https://sportapi7.example.test",
            rapidapi_sofascore_base_url="https://sofascore.example.test",
            rapidapi_sport_api_real_time_base_url="https://realtime.example.test",
            rapidapi_sofascore_sport_api_base_url="https://sportapi.example.test",
            sofascore_public_api_base_url="https://public.example.test",
        ),
        transport=transport,
        source_dir=Path(r"C:\dev\frontend\ullebets-vecel\matches-for-date"),
    )

    assert summary["parity_reports"] == 1
    assert summary["audit_reports"] == 1
    assert database["job_runs"].count_documents() == 1
    assert database["raw_fixtures"].count_documents() == 2
    assert database["fixtures_canonical"].count_documents() == 1
    assert database["fixture_source_links"].count_documents() == 1
    assert database["parity_reports"].count_documents() == 1
    assert database["audit_reports"].count_documents() == 1


def test_run_fixture_ingest_window_live_handles_empty_requested_date_as_no_targets() -> None:
    support_docs = build_support_docs()

    def transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:  # noqa: ARG001
        return HttpJsonResponse(
            status=200,
            headers={"content-type": "application/json"},
            data={"events": []},
        )

    summary = run_fixture_ingest_window(
        mode="live",
        dates=["2026-06-29"],
        support_docs=support_docs,
        source_workflow="import-fixtures-rolling.yml",
        old_payloads_by_date={},
        database=None,
        dry_run=True,
        source_config=FixtureSourceConfig.from_env({}),
        transport=transport,
        source_dir=Path(r"C:\dev\frontend\ullebets-vecel\matches-for-date"),
    )

    assert summary["processed_dates"] == 1
    assert summary["canonical_docs"] == 0
    assert summary["parity_reports"] == 1
    assert summary["audit_reports"] == 1
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}


def test_run_fixture_ingest_window_live_distinguishes_empty_from_source_failure() -> None:
    support_docs = build_support_docs()

    def transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:  # noqa: ARG001
        return HttpJsonResponse(
            status=403,
            headers={"content-type": "application/json"},
            data=None,
        )

    summary = run_fixture_ingest_window(
        mode="live",
        dates=["2026-06-29"],
        support_docs=support_docs,
        source_workflow="import-fixtures-rolling.yml",
        old_payloads_by_date={},
        database=None,
        dry_run=True,
        source_config=FixtureSourceConfig.from_env({}),
        transport=transport,
        source_dir=Path(r"C:\dev\frontend\ullebets-vecel\matches-for-date"),
    )

    assert summary["processed_dates"] == 1
    assert summary["canonical_docs"] == 0
    assert summary["parity_reports"] == 1
    assert summary["audit_reports"] == 1
    assert summary["parity_status_counts"] == {"missing_oracle": 1}
    assert summary["audit_status_counts"] == {"warn": 1}


def test_fixture_reports_mark_missing_old_oracle() -> None:
    support_docs = build_support_docs()
    old_payload = build_old_fixture_payload()
    docs = build_fixture_documents(
        payload=old_payload,
        support_docs=support_docs,
        source_path=Path(r"C:\dev\frontend\ullebets-vecel\matches-for-date\fixtures-2025-10-08.json"),
    )

    parity_rows = build_fixture_parity_rows(
        old_workflow="import-fixtures-rolling.yml",
        old_payloads_by_date={},
        canonical_fixture_docs=docs["canonical"],
        source_link_docs=[],
    )
    audit_rows = build_fixture_audit_rows(
        source_workflow="import-fixtures-rolling.yml",
        raw_fixture_docs=[],
        canonical_fixture_docs=docs["canonical"],
        source_link_docs=[],
        old_payloads_by_date={},
    )

    assert parity_rows[0]["parity_status"] == "missing_oracle"
    assert "missing_old_match_for_date" in parity_rows[0]["blocking_issues"][0]
    assert audit_rows[0]["status"] == "warn"
