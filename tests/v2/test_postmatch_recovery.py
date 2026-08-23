from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.forward_v2 import ingest_match_enrichment
from scripts.forward_v2.ingest_match_enrichment import load_fixture_targets_from_database
from ullebets_v2.enrichment import service as enrichment_service


class FixtureCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        query = query or {}
        rows = list(self.docs)
        for field_name in ("source_date", "fixture_date_stockholm"):
            if field_name in query:
                allowed = set(query[field_name]["$in"])
                rows = [row for row in rows if row.get(field_name) in allowed]
        if "match_key" in query:
            allowed = set(query["match_key"]["$in"])
            rows = [row for row in rows if row.get("match_key") in allowed]
        return rows


def _forward_bet(*, prediction_key: str, match_key: str, start: datetime) -> dict:
    return {
        "prediction_key": prediction_key,
        "selection_key": prediction_key,
        "match_key": match_key,
        "match_start_time": start,
        "saved_at": start - timedelta(hours=2),
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "away",
        "direction": "under",
        "line_value": 4.5,
        "saved_odds": 2.0,
    }


def test_enrichment_date_targets_use_product_date_not_mutable_source_date() -> None:
    database = {
        "fixtures_canonical": FixtureCollection(
            [
                {
                    "match_key": "wanted",
                    "source_date": "2026-08-30",
                    "fixture_date_stockholm": "2026-08-22",
                    "start_time": datetime(2026, 8, 22, 18, 45, tzinfo=UTC),
                },
                {
                    "match_key": "wrong",
                    "source_date": "2026-08-22",
                    "fixture_date_stockholm": "2026-08-30",
                    "start_time": datetime(2026, 8, 30, 18, 45, tzinfo=UTC),
                },
            ]
        )
    }

    targets = load_fixture_targets_from_database(database, ["2026-08-22"])

    assert [row["match_key"] for row in targets] == ["wanted"]


def test_unresolved_forward_targets_are_old_unsettled_matches_deduplicated() -> None:
    selector = getattr(enrichment_service, "select_unresolved_forward_match_keys", None)
    assert callable(selector), "postmatch recovery selector is missing"

    reference_time = datetime(2026, 8, 23, 18, 0, tzinfo=UTC)
    old_start = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)
    recent_start = datetime(2026, 8, 23, 17, 0, tzinfo=UTC)
    forward_bets = [
        _forward_bet(prediction_key="old-1", match_key="old-unresolved", start=old_start),
        _forward_bet(prediction_key="old-2", match_key="old-unresolved", start=old_start),
        _forward_bet(prediction_key="resolved", match_key="resolved", start=old_start),
        _forward_bet(prediction_key="recent", match_key="recent", start=recent_start),
    ]
    results = [
        {
            "match_key": "resolved",
            "home_score": 1,
            "away_score": 0,
        }
    ]
    stats = [
        {
            "match_key": "resolved",
            "stat_key": "cornerKicks",
            "period": "ALL",
            "scope": "away",
            "actual_value": 3,
        }
    ]

    match_keys = selector(
        forward_bet_docs=forward_bets,
        match_stats_canonical=stats,
        match_results_canonical=results,
        reference_time=reference_time,
        minimum_match_age=timedelta(hours=3),
    )

    assert match_keys == ["old-unresolved"]


def test_unresolved_forward_fixture_loader_returns_only_recovery_targets() -> None:
    loader = getattr(ingest_match_enrichment, "load_unresolved_forward_fixture_targets", None)
    assert callable(loader), "database-backed postmatch recovery loader is missing"

    reference_time = datetime(2026, 8, 23, 18, 0, tzinfo=UTC)
    old_start = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)
    database = {
        "forward_bets": FixtureCollection(
            [
                _forward_bet(
                    prediction_key="old",
                    match_key="old-unresolved",
                    start=old_start,
                )
            ]
        ),
        "match_stats_canonical": FixtureCollection([]),
        "match_results_canonical": FixtureCollection([]),
        "fixtures_canonical": FixtureCollection(
            [
                {
                    "match_key": "old-unresolved",
                    "fixture_date_stockholm": "2026-08-22",
                    "start_time": old_start,
                },
                {
                    "match_key": "unrelated",
                    "fixture_date_stockholm": "2026-08-22",
                    "start_time": old_start,
                },
            ]
        ),
    }

    targets = loader(
        database,
        reference_time=reference_time,
        minimum_match_age=timedelta(hours=3),
    )

    assert [row["match_key"] for row in targets] == ["old-unresolved"]
