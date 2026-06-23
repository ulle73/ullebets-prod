from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.odds.service import inspect_fixture_target_window_from_database, load_fixture_targets_from_database


class FakeCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        query = query or {}
        rows = list(self.docs)
        if "source_date" in query:
            allowed = set(query["source_date"]["$in"])
            rows = [row for row in rows if row.get("source_date") in allowed]
        if "start_time" in query:
            start = query["start_time"]["$gte"]
            end = query["start_time"]["$lte"]
            rows = [row for row in rows if start <= row.get("start_time") <= end]
        if "league_name" in query:
            rows = [row for row in rows if row.get("league_name") == query["league_name"]]
        return rows


class FakeDatabase(dict):
    def __getitem__(self, collection_name: str):
        return dict.__getitem__(self, collection_name)


def build_database() -> FakeDatabase:
    database = FakeDatabase()
    database["fixtures_canonical"] = FakeCollection(
        [
            {
                "match_key": "m2",
                "source_date": "2025-10-09",
                "league_name": "La Liga",
                "start_time": datetime(2025, 10, 9, 18, 0, tzinfo=UTC),
            },
            {
                "match_key": "m1",
                "source_date": "2025-10-08",
                "league_name": "Premier League",
                "start_time": datetime(2025, 10, 8, 18, 0, tzinfo=UTC),
            },
            {
                "match_key": "m3",
                "source_date": "2025-10-20",
                "league_name": "Premier League",
                "start_time": datetime(2025, 10, 20, 18, 0, tzinfo=UTC),
            },
        ]
    )
    return database


def test_load_fixture_targets_from_database_filters_by_dates_and_sorts() -> None:
    targets = load_fixture_targets_from_database(
        database=build_database(),
        dates=["2025-10-09", "2025-10-08"],
    )

    assert [row["match_key"] for row in targets] == ["m1", "m2"]


def test_load_fixture_targets_from_database_uses_future_window_and_league_filter() -> None:
    targets = load_fixture_targets_from_database(
        database=build_database(),
        max_days_ahead=3,
        reference_time=datetime(2025, 10, 8, 0, 0, tzinfo=UTC),
        league_name="Premier League",
    )

    assert [row["match_key"] for row in targets] == ["m1"]


def test_inspect_fixture_target_window_from_database_flags_empty_requested_window_with_later_fixtures() -> None:
    context = inspect_fixture_target_window_from_database(
        database=build_database(),
        max_days_ahead=3,
        reference_time=datetime(2025, 10, 10, 0, 0, tzinfo=UTC),
        empty_horizon_days=14,
    )

    assert context["available_target_match_count"] == 0
    assert context["future_fixture_count_in_horizon"] == 1
    assert context["future_fixture_count_after_requested_window"] == 1
    assert context["empty_reason"] == "no_fixtures_in_requested_window_but_present_later"
    assert context["next_fixture_match_key"] == "m3"


def test_inspect_fixture_target_window_from_database_flags_empty_source_horizon() -> None:
    context = inspect_fixture_target_window_from_database(
        database=build_database(),
        max_days_ahead=7,
        reference_time=datetime(2025, 11, 30, 0, 0, tzinfo=UTC),
        empty_horizon_days=35,
    )

    assert context["available_target_match_count"] == 0
    assert context["future_fixture_count_in_horizon"] == 0
    assert context["empty_reason"] == "no_fixtures_in_source_horizon"
