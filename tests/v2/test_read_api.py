from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.read_api.service import read_auto, read_dashboard, read_match_detail, read_results


class FakeCursor(list):
    def sort(self, spec):
        rows = list(self)
        for field, direction in reversed(spec):
            rows.sort(key=lambda row: row.get(field) or "", reverse=direction < 0)
        return FakeCursor(rows)

    def limit(self, value: int):
        return FakeCursor(self[:value])


class FakeCollection:
    def __init__(self, rows):
        self.rows = list(rows)

    @staticmethod
    def _matches(row, query):
        for key, expected in query.items():
            actual = row.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
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


class FakeDatabase(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


def fixture_row() -> dict:
    return {
        "match_key": "sofascore:123",
        "source_date": "2026-08-09",
        "start_time": datetime(2026, 8, 9, 18, 0, tzinfo=UTC),
        "league_name": "Test League",
        "home_team_key": "home",
        "away_team_key": "away",
        "home_team_name": "Home FC",
        "away_team_name": "Away FC",
        "status_type": "notstarted",
    }


def matchup_row() -> dict:
    return {
        "entry_key": "row-1",
        "snapshot_date": "2026-08-09",
        "match_key": "sofascore:123",
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


def test_dashboard_reads_persisted_matchups_instead_of_frontend_fallbacks() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row()]),
        matchups_score=FakeCollection([matchup_row()]),
    )

    payload = read_dashboard(database, source_date="2026-08-09")

    assert payload["selectedDate"] == "2026-08-09"
    assert payload["matches"][0]["homeTeamName"] == "Home FC"
    assert payload["matchups"][0]["score"] == 73.4
    assert payload["matchups"][0]["leagueBaseline"] == 12.6
    assert payload["matchups"][0]["condition"] == "OVER"


def test_dashboard_does_not_recompute_missing_persisted_matchups() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row()]),
        matchups_score=FakeCollection([]),
    )

    payload = read_dashboard(database, source_date="2026-08-09")

    assert len(payload["matches"]) == 1
    assert payload["matchups"] == []


def test_dashboard_has_no_synthetic_fallback_when_date_has_no_rows() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([]),
        matchups_score=FakeCollection([]),
    )

    payload = read_dashboard(database, source_date="2099-01-01")

    assert payload == {"selectedDate": "2099-01-01", "matches": [], "matchups": []}


def profile(team_key: str, match_type: str, profile_date: str, value: float) -> dict:
    return {
        "team_key": team_key,
        "match_type": match_type,
        "profile_date": profile_date,
        "generated_at": datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        "statistics": {
            "for": {"fouls": {"ALL": {"value": value, "rank": 1}}},
            "leagueAverage": {"for": {"fouls": {"ALL": {"value": 11.0}}}},
        },
    }


def test_historical_match_detail_uses_profile_as_of_match_date_not_current_profile() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row()]),
        matchups_score=FakeCollection([matchup_row()]),
        matchups_league_avg=FakeCollection([]),
        market_snapshots=FakeCollection([]),
        teamprofiles=FakeCollection(
            [
                profile("home", "home", "current", 99.0),
                profile("home", "home", "2026-08-09", 10.0),
                profile("away", "away", "current", 88.0),
                profile("away", "away", "2026-08-09", 12.0),
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

    assert payload["count"] == 2
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

    assert payload["summary"] == {"rows": 2, "settled": 1, "wins": 1, "losses": 0, "excluded": 1}
    assert len(payload["rows"]) == 1
