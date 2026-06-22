from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.odds.discovery import extract_event_list, find_unibet_event_for_match
from ullebets_v2.odds.mapper import map_unibet_odds
from ullebets_v2.odds.persistence import persist_odds_records
from ullebets_v2.odds.service import build_smoke_targets_for_league, run_unibet_odds_ingest


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


class FakeOracle:
    def lookup_event(self, match_info: dict) -> dict:
        return {
            "eventId": "evt-1",
            "homeTeam": match_info["homeTeam"],
            "awayTeam": match_info["awayTeam"],
        }

    def map_odds(self, bet_offers: list[dict], home_team: str, away_team: str) -> list[dict]:
        return map_unibet_odds(bet_offers, home_team, away_team)


def build_support_docs() -> dict:
    return {
        "leagues": [
            {
                "league_key": "premier-league",
                "league_name": "Premier League",
                "unibet_base_url": "https://example.test/premier-league/listview.json",
                "unibet_lookup_slugs": ["premier league"],
            }
        ],
        "teams": [
            {"team_name": "Arsenal"},
            {"team_name": "Bournemouth"},
        ],
    }


def build_list_view_payload() -> dict:
    return {
        "events": [
            {
                "event": {
                    "id": "evt-2",
                    "homeName": "Arsenal",
                    "awayName": "Bournemouth",
                    "start": "2026-06-23T18:00:00Z",
                    "group": "Wrong League",
                }
            },
            {
                "event": {
                    "id": "evt-1",
                    "homeName": "Bournemouth",
                    "awayName": "Arsenal",
                    "start": "2026-06-22T18:00:00Z",
                    "group": "Premier League",
                }
            },
        ]
    }


def build_event_payload() -> dict:
    return {
        "betOffers": [
            {
                "criterion": {"label": "Antal hörnor"},
                "outcomes": [
                    {"label": "Över", "englishLabel": "Over", "odds": 1500, "line": 3500},
                    {"label": "Under", "englishLabel": "Under", "odds": 2500, "line": 3500},
                ],
            }
        ]
    }


def fake_transport(url: str, headers: dict[str, str], timeout_seconds: int):  # noqa: ARG001
    class Response:
        def __init__(self, status: int, data: dict) -> None:
            self.status = status
            self.data = data
            self.headers = {}

    if "betoffer/event/" in url:
        return Response(200, build_event_payload())
    return Response(200, build_list_view_payload())


def test_map_unibet_odds_matches_original_mapper_behavior() -> None:
    legacy = map_unibet_odds(
        [
            {
                "criterion": {"label": "Totala hörnor"},
                "outcomes": [
                    {"label": "Över", "englishLabel": "Over", "odds": 1500, "line": 3500},
                    {"label": "Under", "englishLabel": "Under", "odds": 2500, "line": 3500},
                ],
            }
        ],
        "Arsenal",
        "Bournemouth",
    )
    player_specific = map_unibet_odds(
        [
            {
                "criterion": {"label": "Antal skott på mål av spelaren (avgörs genom Opta Data)"},
                "outcomes": [
                    {"label": "Över", "englishLabel": "Over", "odds": 5800, "line": 500},
                ],
            }
        ],
        "Arsenal",
        "Bournemouth",
    )

    assert len(legacy) == 1
    assert legacy[0]["statKey"] == "cornerKicks"
    assert legacy[0]["odds"] == {"over": 1.5, "under": 2.5}
    assert player_specific == []


def test_find_unibet_event_for_match_prefers_league_and_swapped_team_order() -> None:
    support_docs = build_support_docs()
    match = {
        "match_key": "match-1",
        "league_name": "Premier League",
        "home_team_name": "Arsenal",
        "away_team_name": "Bournemouth",
        "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
    }

    discovered = find_unibet_event_for_match(
        match=match,
        list_view_events=extract_event_list(build_list_view_payload()),
        support_docs=support_docs,
    )

    assert discovered is not None
    assert discovered.event_id == "evt-1"
    assert discovered.home_team_name == "Arsenal"
    assert discovered.away_team_name == "Bournemouth"


def test_build_smoke_targets_for_league_filters_to_requested_window() -> None:
    targets = build_smoke_targets_for_league(
        league_name="Premier League",
        support_docs=build_support_docs(),
        transport=fake_transport,
        limit=5,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
        reference_time=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
        max_days_ahead=2,
    )

    assert [target["match_key"] for target in targets] == ["smoke:evt-1"]


def test_persist_odds_records_is_rerun_safe() -> None:
    database = FakeDatabase()
    metrics_first = persist_odds_records(
        database,
        raw_docs=[
            {
                "raw_key": "list_view|premier-league|2026-06-22T10:00:00+00:00|abc",
                "payload_hash": "abc",
                "payload_kind": "list_view",
            }
        ],
        event_link_docs=[{"event_id": "evt-1", "match_key": "match-1"}],
        market_offer_docs=[{"offer_key": "match-1|cornerKicks|total|ALL|3.5"}],
        parity_rows=[
            {
                "old_workflow": "run-unibet-forward.yml",
                "report_date": "2026-06-22",
            }
        ],
        audit_rows=[
            {
                "audit_type": "odds_ingest",
                "scope_key": "run-unibet-forward.yml",
                "report_date": "2026-06-22",
            }
        ],
        health_rows=[
            {
                "job_name": "ingest_unibet_odds",
                "report_date": "2026-06-22",
            }
        ],
    )
    metrics_second = persist_odds_records(
        database,
        raw_docs=[
            {
                "raw_key": "list_view|premier-league|2026-06-22T10:00:00+00:00|abc",
                "payload_hash": "abc",
                "payload_kind": "list_view",
            }
        ],
        event_link_docs=[{"event_id": "evt-1", "match_key": "match-1"}],
        market_offer_docs=[{"offer_key": "match-1|cornerKicks|total|ALL|3.5"}],
        parity_rows=[
            {
                "old_workflow": "run-unibet-forward.yml",
                "report_date": "2026-06-22",
            }
        ],
        audit_rows=[
            {
                "audit_type": "odds_ingest",
                "scope_key": "run-unibet-forward.yml",
                "report_date": "2026-06-22",
            }
        ],
        health_rows=[
            {
                "job_name": "ingest_unibet_odds",
                "report_date": "2026-06-22",
            }
        ],
    )

    assert metrics_first["raw_upserts"] == 1
    assert metrics_second["raw_upserts"] == 0
    assert database["raw_odds_kambi"].count_documents() == 1
    assert database["unibet_event_links"].count_documents() == 1
    assert database["market_offers"].count_documents() == 1
    assert database["parity_reports"].count_documents() == 1
    assert database["audit_reports"].count_documents() == 1
    assert database["health_reports"].count_documents() == 1


def test_run_unibet_odds_ingest_dry_run_matches_oracle() -> None:
    summary = run_unibet_odds_ingest(
        targets=[
            {
                "match_key": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
            }
        ],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-forward.yml",
        dry_run=True,
        transport=fake_transport,
        oracle=FakeOracle(),
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["matched_events"] == 1
    assert summary["raw_docs"] == 2
    assert summary["event_links"] == 1
    assert summary["market_offers"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    assert summary["match_rows"][0]["v2_event_id"] == "evt-1"
    assert summary["match_rows"][0]["oracle_event_id"] == "evt-1"


def test_run_unibet_odds_ingest_dry_run_handles_empty_target_window() -> None:
    summary = run_unibet_odds_ingest(
        targets=[],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-forward.yml",
        dry_run=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["target_matches"] == 0
    assert summary["raw_docs"] == 0
    assert summary["event_links"] == 0
    assert summary["market_offers"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
