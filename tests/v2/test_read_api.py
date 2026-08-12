from __future__ import annotations

from datetime import UTC, datetime

import ullebets_v2.read_api.service as read_service
from ullebets_v2.read_api.service import read_auto, read_dashboard, read_match_detail, read_results


class FakeCursor(list):
    def sort(self, spec):
        rows = list(self)
        for field, direction in reversed(spec):
            rows.sort(key=lambda row: row.get(field) or "", reverse=direction < 0)
        return FakeCursor(rows)

    def skip(self, value: int):
        return FakeCursor(self[value:])

    def limit(self, value: int):
        return FakeCursor(self[:value])


class FakeCollection:
    def __init__(self, rows=()):
        self.rows = list(rows)

    @staticmethod
    def _matches(row, query):
        for key, expected in query.items():
            actual = row.get(key)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query=None, projection=None):
        del projection
        query = query or {}
        return FakeCursor([row.copy() for row in self.rows if self._matches(row, query)])

    def find_one(self, query=None, projection=None, sort=None):
        cursor = self.find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        return cursor[0] if cursor else None

    def count_documents(self, query=None):
        query = query or {}
        return sum(1 for row in self.rows if self._matches(row, query))

    def distinct(self, field, query=None):
        query = query or {}
        return list(dict.fromkeys(row.get(field) for row in self.rows if self._matches(row, query) and row.get(field) is not None))


class FakeDatabase(dict):
    def __getitem__(self, key):
        return self.get(key, FakeCollection())


def fixture_row(*, source_date: str = "2026-08-09", start_time: datetime | None = None) -> dict:
    return {
        "match_key": "sofascore:123",
        "source_date": source_date,
        "start_time": start_time or datetime(2026, 8, 9, 18, 0, tzinfo=UTC),
        "league_key": "test-league",
        "league_name": "Test League",
        "home_team_key": "home",
        "away_team_key": "away",
        "home_team_name": "Home FC",
        "away_team_name": "Away FC",
        "status_type": "notstarted",
    }


def matchup_row(*, snapshot_date: str = "2026-08-09") -> dict:
    return {
        "entry_key": "row-1",
        "snapshot_date": snapshot_date,
        "match_key": "sofascore:123",
        "league_key": "test-league",
        "league_name": "Test League",
        "home_team_name": "Home FC",
        "away_team_name": "Away FC",
        "stat_key": "fouls",
        "stat_label": "Fouls",
        "period": "ALL",
        "period_label": "Hela matchen",
        "scope": "away",
        "condition": "over",
        "score": 73.4,
        "rank_position": 1,
        "is_top_50": True,
        "market_bias": None,
        "forecast": {"leagueBaseline": 12.6},
    }


def profile(team_key: str, match_type: str, profile_date: str, value: float) -> dict:
    return {
        "team_key": team_key,
        "league_key": "test-league",
        "match_type": match_type,
        "profile_date": profile_date,
        "generated_at": datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        "games": [{"match_key": f"history-{team_key}"}] * 6,
        "statistics": {
            "for": {"fouls": {"ALL": {"value": value, "rank": 1}}},
            "against": {"fouls": {"ALL": {"value": value - 1, "rank": 2}}},
            "leagueAverage": {"for": {"fouls": {"ALL": {"value": 11.0}}}},
        },
        "specials": {},
    }


def test_dashboard_reads_persisted_matchups_instead_of_recomputing(monkeypatch) -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row()]),
        matchups_score=FakeCollection([matchup_row()]),
    )

    def fail_if_called(**_kwargs):
        raise AssertionError("persisted matchups must win over read-time computation")

    monkeypatch.setattr(read_service, "build_matchups_score_docs", fail_if_called, raising=False)
    payload = read_dashboard(database, source_date="2026-08-09")

    assert payload["selectedDate"] == "2026-08-09"
    assert payload["matches"][0]["homeTeamName"] == "Home FC"
    assert payload["matchups"][0]["score"] == 73.4
    assert payload["matchups"][0]["leagueBaseline"] == 12.6
    assert payload["matchups"][0]["condition"] == "OVER"
    assert payload["matchupSource"] == "persisted"


def test_dashboard_can_compute_upcoming_matchups_read_only_from_current_profiles(monkeypatch) -> None:
    future_date = "2099-01-01"
    future_start = datetime(2099, 1, 1, 18, 0, tzinfo=UTC)
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row(source_date=future_date, start_time=future_start)]),
        matchups_score=FakeCollection([]),
        teamprofiles=FakeCollection(
            [
                profile("home", "home", "current", 10.0),
                profile("away", "away", "current", 12.0),
            ]
        ),
    )
    captured = {}

    def fake_builder(*, target_matches, teamprofile_docs, snapshot_date, **_kwargs):
        captured["target_matches"] = target_matches
        captured["teamprofile_docs"] = teamprofile_docs
        captured["snapshot_date"] = snapshot_date
        return [matchup_row(snapshot_date=future_date)], []

    monkeypatch.setattr(read_service, "build_matchups_score_docs", fake_builder, raising=False)
    payload = read_dashboard(database, source_date=future_date)

    assert payload["matchupSource"] == "computed_read_only"
    assert payload["matchups"][0]["score"] == 73.4
    assert captured["snapshot_date"] == future_date
    assert [row["profile_date"] for row in captured["teamprofile_docs"]] == ["current", "current"]
    assert captured["target_matches"][0]["match_key"] == "sofascore:123"


def test_dashboard_never_recomputes_started_or_historical_matchups(monkeypatch) -> None:
    historical_date = "2000-01-01"
    database = FakeDatabase(
        fixtures_canonical=FakeCollection(
            [fixture_row(source_date=historical_date, start_time=datetime(2000, 1, 1, 18, 0, tzinfo=UTC))]
        ),
        matchups_score=FakeCollection([]),
        teamprofiles=FakeCollection(
            [
                profile("home", "home", "current", 99.0),
                profile("away", "away", "current", 88.0),
            ]
        ),
    )

    def fail_if_called(**_kwargs):
        raise AssertionError("historical matchups must never use today's profiles")

    monkeypatch.setattr(read_service, "build_matchups_score_docs", fail_if_called, raising=False)
    payload = read_dashboard(database, source_date=historical_date)

    assert payload["matchups"] == []
    assert payload["matchupSource"] == "missing"


def test_dashboard_has_no_synthetic_fallback_when_date_has_no_rows() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([]),
        matchups_score=FakeCollection([]),
    )

    payload = read_dashboard(database, source_date="2099-01-01")

    assert payload["selectedDate"] == "2099-01-01"
    assert payload["timezone"] == "Europe/Stockholm"
    assert payload["generatedAt"].endswith("Z")
    assert payload["matches"] == []
    assert payload["matchups"] == []
    assert payload["matchupSource"] == "missing"


def test_historical_match_detail_uses_profile_as_of_match_date_not_current_profile() -> None:
    historical_date = "2000-01-01"
    database = FakeDatabase(
        fixtures_canonical=FakeCollection(
            [fixture_row(source_date=historical_date, start_time=datetime(2000, 1, 1, 18, 0, tzinfo=UTC))]
        ),
        matchups_score=FakeCollection([]),
        matchups_league_avg=FakeCollection([]),
        market_snapshots=FakeCollection([]),
        teamprofiles=FakeCollection(
            [
                profile("home", "home", "current", 99.0),
                profile("home", "home", historical_date, 10.0),
                profile("away", "away", "current", 88.0),
                profile("away", "away", historical_date, 12.0),
            ]
        ),
    )

    payload = read_match_detail(database, "sofascore:123")

    assert payload is not None
    assert payload["teamStats"][0]["homeValue"] == 10.0
    assert payload["teamStats"][0]["awayValue"] == 12.0


def test_auto_count_covers_full_collection_even_when_rows_are_limited() -> None:
    database = FakeDatabase(
        forward_bets=FakeCollection(
            [
                {"selection_key": "s1", "match_key": "m1", "match_start_time": datetime(2026, 8, 9, 12, tzinfo=UTC)},
                {"selection_key": "s2", "match_key": "m2", "match_start_time": datetime(2026, 8, 8, 12, tzinfo=UTC)},
            ]
        ),
        fixtures_canonical=FakeCollection([]),
    )

    payload = read_auto(database, limit=1)

    assert payload["summary"]["total"] == 2
    assert payload["page"] == {"limit": 1, "offset": 0, "hasMore": True}
    assert len(payload["selections"]) == 1


def test_results_summary_covers_full_collection_even_when_rows_are_limited() -> None:
    database = FakeDatabase(
        forward_results=FakeCollection(
            [
                {"result_loop_key": "r1", "settlement_status": "settled", "valid_for_performance": True, "win": True, "match_start_time": datetime(2026, 8, 9, 12, tzinfo=UTC)},
                {"result_loop_key": "r2", "settlement_status": "settled", "valid_for_performance": False, "win": False, "match_start_time": datetime(2026, 8, 8, 12, tzinfo=UTC)},
            ]
        )
    )

    payload = read_results(database, limit=1)

    assert payload["summary"] == {"rows": 2, "settled": 1, "wins": 1, "losses": 0, "pushes": 0, "excluded": 1}
    assert payload["page"] == {"limit": 1, "offset": 0, "hasMore": True}
    assert len(payload["rows"]) == 1
