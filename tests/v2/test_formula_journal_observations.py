from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from ullebets_v2.formula_journal.observations import (
    ImmutableFormulaObservationConflict,
    build_js_observation_docs,
    build_ml_observation_docs,
    persist_formula_observations,
)


NOW = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
KICKOFF = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)


def _registry() -> dict:
    return {
        "registry_id": "shadow_formula_registry_v1",
        "js_formulas": {
            "evPct": {"label": "Basformel", "family": "heuristic"},
            "evPctLeagueAvg": {"label": "Liga-snitt", "family": "heuristic"},
        },
        "frozen_models": [
            {
                "model_id": "ev_scope_v6",
                "label": "V6 scope interaction",
                "family": "frozen_ml",
            }
        ],
    }


def _context(*, snapshot_label: str = "T_MINUS_2H") -> dict:
    return {
        "match_key": "match-1",
        "league_key": "premier-league",
        "league_name": "Premier League",
        "home_team_name": "Arsenal",
        "away_team_name": "Bournemouth",
        "match_start_time": KICKOFF,
        "snapshot_key": f"match-1|corners|{snapshot_label}",
        "snapshot_label": snapshot_label,
        "snapshot_type": "checkpoint",
        "odds_snapshot_time": NOW,
    }


def _js_line() -> dict:
    return {
        "betKey": "match-1|corners|total|ALL|9.5|over",
        "statKey": "cornerKicks",
        "scope": "total",
        "period": "ALL",
        "line": 9.5,
        "direction": "over",
        "odds": 2.0,
        "evDetails": {"evPct": 10.0, "evPctLeagueAvg": 4.0},
    }


def _ml_score(*, valid: bool = True) -> dict:
    return {
        "score_key": "ev_scope_v6|snapshot-1|over",
        "model_id": "ev_scope_v6",
        "artifact_sha256": "b" * 64,
        "match_key": "match-1",
        "snapshot_key": "snapshot-1",
        "snapshot_label": "T_MINUS_2H",
        "snapshot_type": "checkpoint",
        "stat_key": "cornerKicks",
        "scope": "total",
        "period": "ALL",
        "line_value": 9.5,
        "direction": "over",
        "offered_odds": 2.0,
        "predicted_win_probability": 0.55,
        "expected_roi_units": 0.10,
        "odds_snapshot_time": NOW,
        "match_start_time": KICKOFF,
        "score_created_at": NOW,
        "valid_for_policy_evaluation": valid,
        "invalid_for_model": not valid,
    }


class FakeCollection:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.find_calls = 0
        self.bulk_write_calls = 0

    def find(self, query: dict, projection: dict | None = None):  # noqa: ANN201, ARG002
        self.find_calls += 1
        keys = set(query["observation_key"]["$in"])
        return [deepcopy(row) for key, row in self.rows.items() if key in keys]

    def bulk_write(self, operations: list, *, ordered: bool = False) -> SimpleNamespace:
        assert ordered is False
        self.bulk_write_calls += 1
        upserted_count = 0
        for operation in operations:
            key = operation._filter["observation_key"]
            if key not in self.rows:
                self.rows[key] = deepcopy(operation._doc["$setOnInsert"])
                upserted_count += 1
        return SimpleNamespace(upserted_count=upserted_count)

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:  # noqa: ARG002
        row = self.rows.get(query["observation_key"])
        return deepcopy(row) if row is not None else None

    def update_one(self, query: dict, update: dict, *, upsert: bool = False) -> SimpleNamespace:
        assert upsert is True
        key = query["observation_key"]
        if key in self.rows:
            return SimpleNamespace(upserted_id=None)
        self.rows[key] = deepcopy(update["$setOnInsert"])
        return SimpleNamespace(upserted_id=key)


def test_js_formula_values_become_independent_shadow_observations() -> None:
    docs = build_js_observation_docs(
        lines=[_js_line()],
        context=_context(),
        runtime_sha256="a" * 64,
        registry=_registry(),
        journaled_at=NOW,
    )

    assert {row["formula_id"] for row in docs} == {
        "js:evPct",
        "js:evPctLeagueAvg",
    }
    assert {row["predicted_win_probability"] for row in docs} == {0.55, 0.52}
    assert all(row["shadow_stake_units"] == 1.0 for row in docs)
    assert all(row["valid_for_comparison"] is True for row in docs)
    assert all(row["prediction_created_at"] == NOW for row in docs)
    assert len({row["observation_key"] for row in docs}) == 2


def test_js_replay_uses_snapshot_time_and_a_versioned_schema_identity() -> None:
    first = build_js_observation_docs(
        lines=[_js_line()],
        context=_context(),
        runtime_sha256="a" * 64,
        registry=_registry(),
        journaled_at=NOW,
    )
    replay = build_js_observation_docs(
        lines=[_js_line()],
        context=_context(),
        runtime_sha256="a" * 64,
        registry=_registry(),
        journaled_at=NOW.replace(minute=30),
    )

    assert [row["observation_key"] for row in replay] == [
        row["observation_key"] for row in first
    ]
    assert [row["observation_fingerprint_sha256"] for row in replay] == [
        row["observation_fingerprint_sha256"] for row in first
    ]
    assert all(row["prediction_created_at"] == NOW for row in replay)
    assert all(row["observation_schema_version"] == "js-v2" for row in replay)
    assert all(row["formula_version"].endswith(":js-v2") for row in replay)


def test_unregistered_numeric_js_formula_is_still_archived_with_stable_fallback_metadata() -> None:
    line = _js_line()
    line["evDetails"] = {"evPctNewRuntimeFormula": -2.0}

    [doc] = build_js_observation_docs(
        lines=[line],
        context=_context(),
        runtime_sha256="a" * 64,
        registry=_registry(),
        journaled_at=NOW,
    )

    assert doc["formula_id"] == "js:evPctNewRuntimeFormula"
    assert doc["formula_label"] == "evPctNewRuntimeFormula"
    assert doc["formula_family"] == "js_formula"
    assert doc["is_positive_ev"] is False
    assert doc["shadow_stake_units"] == 0.0
    assert doc["exclusion_reason"] == "not_positive_ev"


def test_out_of_domain_ml_score_is_archived_without_stake() -> None:
    [doc] = build_ml_observation_docs(
        scores=[_ml_score(valid=False)],
        registry=_registry(),
        fixtures_by_match={"match-1": _context()},
        journaled_at=NOW,
    )

    assert doc["formula_id"] == "ml:ev_scope_v6"
    assert doc["valid_for_comparison"] is False
    assert doc["domain_status"] == "out_of_domain"
    assert doc["shadow_stake_units"] == 0.0
    assert doc["exclusion_reason"] == "out_of_domain"
    assert doc["prediction_created_at"] == NOW


def test_persistence_replays_identical_doc_and_rejects_changed_immutable_evidence() -> None:
    [doc] = build_ml_observation_docs(
        scores=[_ml_score()],
        registry=_registry(),
        fixtures_by_match={"match-1": _context()},
        journaled_at=NOW,
    )
    collection = FakeCollection()

    assert persist_formula_observations(collection, [doc]) == {
        "inserted": 1,
        "existing": 0,
        "conflicts": 0,
    }
    assert persist_formula_observations(collection, [doc]) == {
        "inserted": 0,
        "existing": 1,
        "conflicts": 0,
    }
    assert collection.find_calls == 2
    assert collection.bulk_write_calls == 1

    changed = deepcopy(doc)
    changed["offered_odds"] = 9.0
    with pytest.raises(ImmutableFormulaObservationConflict):
        persist_formula_observations(collection, [changed])


def test_same_market_at_two_checkpoints_gets_two_distinct_observation_keys() -> None:
    t3d = build_js_observation_docs(
        lines=[_js_line()],
        context=_context(snapshot_label="T_MINUS_3D"),
        runtime_sha256="a" * 64,
        registry=_registry(),
        journaled_at=NOW,
    )
    t2h = build_js_observation_docs(
        lines=[_js_line()],
        context=_context(snapshot_label="T_MINUS_2H"),
        runtime_sha256="a" * 64,
        registry=_registry(),
        journaled_at=NOW,
    )

    assert {row["observation_key"] for row in t3d}.isdisjoint(
        {row["observation_key"] for row in t2h}
    )
