from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from ullebets_v2.formula_journal.materialize import (
    fingerprint_js_runtime,
    materialize_formula_observations,
)
from ullebets_v2.storage.collections import (
    EV_MODEL_SCORES,
    FIXTURES_CANONICAL,
    FORMULA_OBSERVATIONS,
    MARKET_SNAPSHOTS,
)


NOW = datetime(2026, 8, 22, 17, 0, tzinfo=UTC)
KICKOFF = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)


class FakeCursor(list):
    def sort(self, spec):
        rows = list(self)
        for field, direction in reversed(spec):
            rows.sort(key=lambda row: row.get(field) or "", reverse=direction < 0)
        return FakeCursor(rows)


class FakeCollection:
    def __init__(self, rows=()) -> None:
        self.rows = [deepcopy(row) for row in rows]

    @staticmethod
    def _matches(row: dict, query: dict) -> bool:
        for key, expected in query.items():
            if key == "$expr":
                continue
            actual = row.get(key)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                    return False
                if "$gt" in expected and (actual is None or actual <= expected["$gt"]):
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query=None, projection=None):  # noqa: ARG002
        return FakeCursor(
            [deepcopy(row) for row in self.rows if self._matches(row, query or {})]
        )

    def find_one(self, query, projection=None):  # noqa: ARG002
        rows = self.find(query)
        return rows[0] if rows else None

    def update_one(self, query, update, *, upsert=False):
        assert upsert is True
        existing = self.find_one(query)
        if existing is not None:
            return SimpleNamespace(upserted_id=None)
        self.rows.append(deepcopy(update["$setOnInsert"]))
        return SimpleNamespace(upserted_id=str(len(self.rows)))

    def bulk_write(self, operations, *, ordered=False):
        assert ordered is False
        upserted_count = 0
        for operation in operations:
            if self.find_one(operation._filter) is None:
                self.rows.append(deepcopy(operation._doc["$setOnInsert"]))
                upserted_count += 1
        return SimpleNamespace(upserted_count=upserted_count)

    def distinct(self, field):
        return sorted({row[field] for row in self.rows if row.get(field) is not None})


class FakeDatabase(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = FakeCollection()
        return super().__getitem__(key)


class FakeOracle:
    def build_match_lines(self, *, match_info, offers, defaults=None):  # noqa: ARG002
        assert match_info["homeTeam"] == "Arsenal"
        [offer] = offers
        return {
            "errors": [],
            "lines": [
                {
                    "betKey": f"{match_info['matchKey']}|{offer['statKey']}|over",
                    "statKey": offer["statKey"],
                    "scope": offer["scope"],
                    "period": offer["period"],
                    "line": offer["line"],
                    "direction": "over",
                    "odds": offer["odds"]["over"],
                    "evDetails": {"evPct": 10.0, "evPctLeagueAvg": 5.0},
                }
            ],
        }


def _registry() -> dict:
    return {
        "registry_id": "shadow_formula_registry_v1",
        "js_formulas": {
            "evPct": {"label": "Bas", "family": "heuristic"},
            "evPctLeagueAvg": {"label": "Liga", "family": "heuristic"},
        },
        "frozen_models": [],
    }


def _snapshot(label: str, hours_before: int) -> dict:
    return {
        "snapshot_key": f"match-1|offer-1|{label}",
        "match_key": "match-1",
        "offer_key": "offer-1",
        "league_key": "premier-league",
        "league_name": "Premier League",
        "home_team_name": "Arsenal",
        "away_team_name": "Bournemouth",
        "stat_key": "cornerKicks",
        "scope": "total",
        "period": "ALL",
        "line": 9.5,
        "over_odds": 2.0,
        "under_odds": 1.8,
        "snapshot_label": label,
        "snapshot_type": "forward",
        "snapshot_time": KICKOFF - timedelta(hours=hours_before),
        "captured_at": KICKOFF - timedelta(hours=hours_before),
        "match_start_time": KICKOFF,
        "invalid_for_model": False,
    }


def _fixture() -> dict:
    return {
        "match_key": "match-1",
        "source_match_id": "123",
        "source_date": "2026-08-22",
        "fixture_date_stockholm": "2026-08-22",
        "start_time": KICKOFF,
        "league_key": "premier-league",
        "league_name": "Premier League",
        "home_team_key": "arsenal",
        "away_team_key": "bournemouth",
        "home_team_name": "Arsenal",
        "away_team_name": "Bournemouth",
    }


def test_materializer_keeps_same_market_at_two_checkpoints_separate() -> None:
    database = FakeDatabase(
        {
            MARKET_SNAPSHOTS: FakeCollection(
                [_snapshot("T_MINUS_3D", 72), _snapshot("T_MINUS_2H", 2)]
            ),
            FIXTURES_CANONICAL: FakeCollection([_fixture()]),
            EV_MODEL_SCORES: FakeCollection(),
            FORMULA_OBSERVATIONS: FakeCollection(),
        }
    )

    summary = materialize_formula_observations(
        database=database,
        oracle=FakeOracle(),
        registry=_registry(),
        runtime_sha256="a" * 64,
        now=NOW,
    )

    assert summary["js_observations"] == 4
    assert summary["oracle_error_count"] == 0
    assert summary["persistence"] == {
        "inserted": 4,
        "existing": 0,
        "conflicts": 0,
    }
    assert database[FORMULA_OBSERVATIONS].distinct("snapshot_label") == [
        "T_MINUS_2H",
        "T_MINUS_3D",
    ]


def test_materializer_replay_is_idempotent() -> None:
    database = FakeDatabase(
        {
            MARKET_SNAPSHOTS: FakeCollection([_snapshot("T_MINUS_2H", 2)]),
            FIXTURES_CANONICAL: FakeCollection([_fixture()]),
            EV_MODEL_SCORES: FakeCollection(),
            FORMULA_OBSERVATIONS: FakeCollection(),
        }
    )

    first = materialize_formula_observations(
        database=database,
        oracle=FakeOracle(),
        registry=_registry(),
        runtime_sha256="a" * 64,
        now=NOW,
    )
    second = materialize_formula_observations(
        database=database,
        oracle=FakeOracle(),
        registry=_registry(),
        runtime_sha256="a" * 64,
        now=NOW,
    )

    assert first["persistence"]["inserted"] == 2
    assert second["persistence"]["existing"] == 2
    assert second["persistence"]["conflicts"] == 0


def test_runtime_fingerprint_changes_when_js_source_changes(tmp_path) -> None:
    (tmp_path / "b.js").write_text("export const b = 1;", encoding="utf-8")
    (tmp_path / "a.js").write_text("export const a = 1;", encoding="utf-8")
    before = fingerprint_js_runtime(tmp_path)
    (tmp_path / "a.js").write_text("export const a = 2;", encoding="utf-8")

    assert before != fingerprint_js_runtime(tmp_path)


def test_runtime_fingerprint_is_independent_of_checkout_line_endings(tmp_path) -> None:
    source = tmp_path / "runtime.js"
    source.write_bytes(b"export const value = 1;\nexport default value;\n")
    unix_fingerprint = fingerprint_js_runtime(tmp_path)
    source.write_bytes(b"export const value = 1;\r\nexport default value;\r\n")

    assert fingerprint_js_runtime(tmp_path) == unix_fingerprint
