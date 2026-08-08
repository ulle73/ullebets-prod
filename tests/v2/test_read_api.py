from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.read_api.service import read_dashboard


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


class FakeDatabase(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


def test_dashboard_reads_persisted_matchups_instead_of_frontend_fallbacks() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection(
            [
                {
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
            ]
        ),
        matchups_score=FakeCollection(
            [
                {
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
            ]
        ),
    )

    payload = read_dashboard(database, source_date="2026-08-09")

    assert payload["selectedDate"] == "2026-08-09"
    assert payload["matches"][0]["homeTeamName"] == "Home FC"
    assert payload["matchups"][0]["score"] == 73.4
    assert payload["matchups"][0]["leagueBaseline"] == 12.6
    assert payload["matchups"][0]["condition"] == "OVER"


def test_dashboard_has_no_synthetic_fallback_when_date_has_no_rows() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([]),
        matchups_score=FakeCollection([]),
    )

    payload = read_dashboard(database, source_date="2099-01-01")

    assert payload == {"selectedDate": "2099-01-01", "matches": [], "matchups": []}
