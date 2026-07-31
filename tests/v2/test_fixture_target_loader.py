from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ullebets_v2.odds.service import (
    inspect_fixture_target_window_from_database,
    load_fixture_targets_from_database,
    load_legacy_backtest_targets,
    load_replay_fixture_targets,
)
from tests.v2.test_odds_ingest import build_legacy_backtest_doc


class FakeCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        query = query or {}
        rows = list(self.docs)
        if "source_date" in query:
            allowed = set(query["source_date"]["$in"])
            rows = [row for row in rows if row.get("source_date") in allowed]
        if "matchDate" in query:
            allowed = set(query["matchDate"]["$in"])
            rows = [row for row in rows if row.get("matchDate") in allowed]
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
                "status_type": "postponed",
            },
            {
                "match_key": "m1",
                "source_date": "2025-10-08",
                "league_name": "Premier League",
                "start_time": datetime(2025, 10, 8, 18, 0, tzinfo=UTC),
                "status_type": "notstarted",
            },
            {
                "match_key": "m3",
                "source_date": "2025-10-20",
                "league_name": "Premier League",
                "start_time": datetime(2025, 10, 20, 18, 0, tzinfo=UTC),
                "status_type": "notstarted",
            },
        ]
    )
    return database


def build_legacy_match_database() -> FakeDatabase:
    database = FakeDatabase()
    database["match-for-date"] = FakeCollection(
        [
            {
                "full": [
                    {
                        "date": "2025-11-21",
                        "savedAt": "2025-11-20T22:00:00Z",
                        "matches": [
                            {
                                "id": 14689178,
                                "startTimestamp": 1763748000,
                                "season": {"id": 1},
                                "status": {"type": "notstarted"},
                                "tournament": {
                                    "uniqueTournament": {
                                        "name": "Premier League",
                                        "slug": "premier-league",
                                        "id": 1,
                                    }
                                },
                                "homeTeam": {"id": 1, "name": "Arsenal"},
                                "awayTeam": {"id": 2, "name": "Bournemouth"},
                            }
                        ],
                    }
                ]
            }
        ]
    )
    return database


def build_legacy_backtest_database() -> FakeDatabase:
    database = FakeDatabase()
    database["unibet-backtest"] = FakeCollection([build_legacy_backtest_doc()])
    database["match-for-date"] = FakeCollection(
        [
            {
                "full": [
                    {
                        "date": "2025-10-08",
                        "savedAt": "2025-10-08T09:00:00Z",
                        "matches": [
                            {
                                "id": 14689178,
                                "startTimestamp": 1759946400,
                                "season": {"id": 1},
                                "status": {"type": "notstarted"},
                                "tournament": {
                                    "uniqueTournament": {
                                        "name": "Premier League",
                                        "slug": "premier-league",
                                        "id": 1,
                                    }
                                },
                                "homeTeam": {"id": 1, "name": "Arsenal"},
                                "awayTeam": {"id": 2, "name": "Bournemouth"},
                            }
                        ],
                    }
                ]
            }
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


def test_load_fixture_targets_from_database_forward_only_excludes_postponed_rows() -> None:
    targets = load_fixture_targets_from_database(
        database=build_database(),
        dates=["2025-10-09", "2025-10-08"],
        forward_only=True,
    )

    assert [row["match_key"] for row in targets] == ["m1"]


def test_inspect_fixture_target_window_from_database_respects_forward_only_filter() -> None:
    context = inspect_fixture_target_window_from_database(
        database=build_database(),
        dates=["2025-10-09"],
        forward_only=True,
    )

    assert context["available_target_match_count"] == 0
    assert context["empty_reason"] == "no_fixtures_for_requested_dates"


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


def test_load_replay_fixture_targets_falls_back_to_legacy_match_database(tmp_path: Path) -> None:
    old_repo_root = tmp_path / "old-repo"
    (old_repo_root / "matches-for-date").mkdir(parents=True, exist_ok=True)
    support_docs = {
        "leagues": [
            {
                "league_key": "premier-league",
                "league_name": "Premier League",
                "league_id": 1,
                "league_slug": "premier-league",
            }
        ],
        "teams": [
            {
                "league_key": "premier-league",
                "team_key": "premier-league:1",
                "team_id": 1,
                "team_name": "Arsenal",
                "team_slug": "arsenal",
            },
            {
                "league_key": "premier-league",
                "team_key": "premier-league:2",
                "team_id": 2,
                "team_name": "Bournemouth",
                "team_slug": "bournemouth",
            },
        ],
    }

    targets = load_replay_fixture_targets(
        dates=["2025-11-21"],
        support_docs=support_docs,
        old_repo_root=old_repo_root,
        legacy_match_database=build_legacy_match_database(),
    )

    assert len(targets) == 1
    assert targets[0]["match_key"] == "sofascore:14689178"
    assert targets[0]["source_date"] == "2025-11-21"
    assert targets[0]["league_name"] == "Premier League"


def test_load_legacy_backtest_targets_builds_canonical_targets_without_fixture_replay() -> None:
    support_docs = {
        "leagues": [
            {
                "league_key": "premier-league",
                "league_name": "Premier League",
                "league_id": 1,
                "league_slug": "premier-league",
            }
        ],
        "teams": [
            {
                "league_key": "premier-league",
                "team_key": "premier-league:arsenal",
                "team_name": "Arsenal",
                "team_slug": "arsenal",
            },
            {
                "league_key": "premier-league",
                "team_key": "premier-league:bournemouth",
                "team_name": "Bournemouth",
                "team_slug": "bournemouth",
            },
        ],
    }

    targets = load_legacy_backtest_targets(
        dates=["2025-10-08"],
        support_docs=support_docs,
        legacy_backtest_database=build_legacy_backtest_database(),
        legacy_match_database=build_legacy_backtest_database(),
    )

    assert len(targets) == 1
    assert targets[0]["match_key"] == "sofascore:14689178"
    assert targets[0]["source_type"] == "legacy_unibet_backtest"
    assert targets[0]["source_date"] == "2025-10-08"
    assert targets[0]["league_key"] == "premier-league"
    assert targets[0]["home_team_key"] == "premier-league:arsenal"
    assert targets[0]["away_team_key"] == "premier-league:bournemouth"
    assert targets[0]["mapping_confidence"] == "support_names"
    assert targets[0]["start_time"] == datetime(2025, 10, 8, 18, 0, tzinfo=UTC)
