from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from ullebets_v2.formula_journal.results import (
    FormulaResultConflict,
    build_formula_result_docs,
    persist_formula_results,
    refresh_formula_results,
)
from ullebets_v2.storage.collections import (
    CLOSING_LINES,
    FORMULA_OBSERVATIONS,
    FORMULA_RESULTS,
    MATCH_RESULTS_CANONICAL,
    MATCH_STATS_CANONICAL,
)


NOW = datetime(2026, 8, 23, 21, 0, tzinfo=UTC)
KICKOFF = NOW - timedelta(hours=3)
SNAPSHOT = KICKOFF - timedelta(hours=2)


def _observation(
    *,
    key: str = "obs-1",
    positive: bool = True,
    valid: bool = True,
    direction: str = "over",
) -> dict:
    return {
        "observation_key": key,
        "source_type": "js_formula",
        "formula_id": "js:evPct",
        "formula_label": "Basformel",
        "formula_family": "heuristic",
        "formula_version": "a" * 64,
        "observation_schema_version": "js-v3",
        "match_key": "match-1",
        "league_key": "premier-league",
        "league_name": "Premier League",
        "home_team_name": "Arsenal",
        "away_team_name": "Bournemouth",
        "snapshot_key": "snapshot-1",
        "offer_key": "offer-1",
        "snapshot_label": "T_MINUS_2H",
        "snapshot_type": "forward",
        "odds_snapshot_time": SNAPSHOT,
        "prediction_created_at": SNAPSHOT,
        "match_start_time": KICKOFF,
        "stat_key": "cornerKicks",
        "scope": "total",
        "period": "ALL",
        "direction": direction,
        "line_value": 4.5,
        "offered_odds": 2.0,
        "predicted_win_probability": 0.55,
        "expected_roi_units": 0.10 if positive else -0.10,
        "expected_ev_pct": 10.0 if positive else -10.0,
        "domain_status": "formula_emitted",
        "valid_for_comparison": valid,
        "is_positive_ev": positive,
        "shadow_stake_units": 1.0 if positive and valid else 0.0,
        "exclusion_reason": None if positive and valid else "not_positive_ev",
    }


def _stats(actual: float = 6) -> list[dict]:
    return [
        {
            "match_key": "match-1",
            "stat_key": "cornerKicks",
            "period": "ALL",
            "scope": "total",
            "actual_value": actual,
        }
    ]


def _results() -> list[dict]:
    return [{"match_key": "match-1", "home_score": 2, "away_score": 1}]


def _closing() -> list[dict]:
    return [
        {
            "closing_key": "offer-1",
            "offer_key": "offer-1",
            "match_key": "match-1",
            "stat_key": "cornerKicks",
            "period": "ALL",
            "scope": "total",
            "line": 4.5,
            "opening_over_odds": 2.1,
            "latest_over_odds": 1.8,
            "closing_over_odds": 1.8,
            "closing_snapshot_label": "T_MINUS_10M",
            "closing_snapshot_time": KICKOFF - timedelta(minutes=10),
            "closing_quality": "t10",
            "closing_age_minutes": 10,
            "prematch_observation_count": 4,
            "price_history": [],
        }
    ]


class FakeCollection:
    def __init__(self, rows=()) -> None:
        self.rows = [deepcopy(row) for row in rows]
        self.bulk_write_calls = 0

    @staticmethod
    def _matches(row: dict, query: dict) -> bool:
        for key, expected in query.items():
            actual = row.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query=None, projection=None):  # noqa: ARG002
        return [deepcopy(row) for row in self.rows if self._matches(row, query or {})]

    def find_one(self, query, projection=None):  # noqa: ARG002
        rows = self.find(query)
        return rows[0] if rows else None

    def update_one(self, query, update, *, upsert=False):
        for index, row in enumerate(self.rows):
            if self._matches(row, query):
                if "$set" in update:
                    self.rows[index] = {**row, **deepcopy(update["$set"])}
                return SimpleNamespace(upserted_id=None, modified_count=1)
        if not upsert:
            return SimpleNamespace(upserted_id=None, modified_count=0)
        doc = deepcopy(update.get("$setOnInsert") or update.get("$set") or {})
        self.rows.append(doc)
        return SimpleNamespace(upserted_id=str(len(self.rows)), modified_count=0)

    def bulk_write(self, operations, *, ordered=False):
        assert ordered is False
        self.bulk_write_calls += 1
        upserted_count = 0
        matched_count = 0
        for operation in operations:
            existing_index = next(
                (
                    index
                    for index, row in enumerate(self.rows)
                    if self._matches(row, operation._filter)
                ),
                None,
            )
            if existing_index is not None:
                matched_count += 1
                if "$set" in operation._doc:
                    self.rows[existing_index] = {
                        **self.rows[existing_index],
                        **deepcopy(operation._doc["$set"]),
                    }
            elif operation._upsert:
                self.rows.append(
                    deepcopy(
                        operation._doc.get("$setOnInsert")
                        or operation._doc.get("$set")
                        or {}
                    )
                )
                upserted_count += 1
        return SimpleNamespace(
            upserted_count=upserted_count,
            matched_count=matched_count,
        )


class FakeDatabase(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = FakeCollection()
        return super().__getitem__(key)


def test_positive_shadow_observation_is_settled_and_gets_official_clv() -> None:
    [row] = build_formula_result_docs(
        observations=[_observation()],
        match_stats_canonical=_stats(),
        match_results_canonical=_results(),
        closing_line_docs=_closing(),
        refreshed_at=NOW,
    )

    assert row["settlement_status"] == "settled"
    assert row["settlement_result"] == "win"
    assert row["pnl_units"] == 1.0
    assert row["stake_units"] == 1.0
    assert row["official_clv"] is True
    assert row["clv_status"] == "tracked"
    assert row["clv_pct"] == 11.1
    assert row["beat_closing_line"] is True
    assert row["valid_for_performance"] is True


def test_non_positive_score_is_settled_for_calibration_without_virtual_pnl() -> None:
    [row] = build_formula_result_docs(
        observations=[_observation(positive=False)],
        match_stats_canonical=_stats(),
        match_results_canonical=_results(),
        closing_line_docs=_closing(),
        refreshed_at=NOW,
    )

    assert row["settlement_result"] == "win"
    assert row["settlement_valid_for_calibration"] is True
    assert row["stake_units"] == 0.0
    assert row["pnl_units"] == 0.0
    assert row["valid_for_performance"] is False


def test_invalid_domain_observation_is_excluded_from_settlement_and_clv() -> None:
    [row] = build_formula_result_docs(
        observations=[_observation(valid=False)],
        match_stats_canonical=_stats(),
        match_results_canonical=_results(),
        closing_line_docs=_closing(),
        refreshed_at=NOW,
    )

    assert row["settlement_status"] == "excluded"
    assert row["settlement_result"] is None
    assert row["clv_status"] == "excluded"
    assert row["valid_for_performance"] is False


def test_superseded_unversioned_js_observation_is_audited_but_never_staked() -> None:
    observation = _observation()
    observation.pop("observation_schema_version")

    [row] = build_formula_result_docs(
        observations=[observation],
        match_stats_canonical=_stats(),
        match_results_canonical=_results(),
        closing_line_docs=_closing(),
        refreshed_at=NOW,
    )

    assert row["settlement_status"] == "excluded"
    assert row["stake_units"] == 0.0
    assert row["valid_for_performance"] is False
    assert row["exclusion_reason"] == "superseded_js_observation_schema"


def test_superseded_v2_js_observation_is_audited_but_never_staked() -> None:
    observation = _observation()
    observation["observation_schema_version"] = "js-v2"

    [row] = build_formula_result_docs(
        observations=[observation],
        match_stats_canonical=_stats(),
        match_results_canonical=_results(),
        closing_line_docs=_closing(),
        refreshed_at=NOW,
    )

    assert row["settlement_status"] == "excluded"
    assert row["stake_units"] == 0.0
    assert row["valid_for_performance"] is False
    assert row["exclusion_reason"] == "superseded_js_observation_schema"


def test_persisted_settled_outcome_is_immutable_but_clv_can_refresh() -> None:
    [row] = build_formula_result_docs(
        observations=[_observation()],
        match_stats_canonical=_stats(),
        match_results_canonical=_results(),
        closing_line_docs=[],
        refreshed_at=NOW,
    )
    collection = FakeCollection()
    assert persist_formula_results(collection, [row])["inserted"] == 1

    official = deepcopy(row)
    official.update({"clv_status": "tracked", "official_clv": True, "clv_pct": 11.1})
    assert persist_formula_results(collection, [official])["updated"] == 1
    assert collection.bulk_write_calls == 2

    changed_outcome = deepcopy(official)
    changed_outcome["settlement_result"] = "loss"
    with pytest.raises(FormulaResultConflict):
        persist_formula_results(collection, [changed_outcome])


def test_refresh_formula_results_reads_all_sources_and_is_idempotent() -> None:
    database = FakeDatabase(
        {
            FORMULA_OBSERVATIONS: FakeCollection([_observation()]),
            MATCH_STATS_CANONICAL: FakeCollection(_stats()),
            MATCH_RESULTS_CANONICAL: FakeCollection(_results()),
            CLOSING_LINES: FakeCollection(_closing()),
            FORMULA_RESULTS: FakeCollection(),
        }
    )

    first = refresh_formula_results(database=database, refreshed_at=NOW)
    second = refresh_formula_results(database=database, refreshed_at=NOW)

    assert first["result_docs"] == 1
    assert first["persistence"]["inserted"] == 1
    assert second["persistence"]["unchanged"] == 1
