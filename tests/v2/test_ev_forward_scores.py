from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from ullebets_v2.ev_model.forward_scores import (
    audit_forward_score_docs,
    build_forward_score_docs,
    persist_forward_score_docs,
)


class FakeResult:
    def __init__(self, *, upserted: bool) -> None:
        self.upserted_id = "new" if upserted else None


class FakeCollection:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def find_one(
        self,
        query: dict,
        projection: dict | None = None,
    ) -> dict | None:
        return self.rows.get(str(query["score_key"]))

    def update_one(
        self,
        query: dict,
        update: dict,
        *,
        upsert: bool,
    ) -> FakeResult:
        key = str(query["score_key"])
        if key in self.rows:
            return FakeResult(upserted=False)
        self.rows[key] = dict(update["$setOnInsert"])
        return FakeResult(upserted=True)


def _score_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "side_key": "m1|cornerKicks|ALL|total|under",
                "exposure_match_id": "m1",
                "match_key": "m1",
                "snapshot_key": "snap-1",
                "offer_key": "offer-1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "under",
                "line_value": 10.5,
                "offered_odds": 1.95,
                "market_fair_probability_over": 0.48,
                "predicted_win_probability": 0.58,
                "expected_roi_units": 0.131,
                "odds_snapshot_time": "2026-07-30T10:00:00Z",
                "match_start_time": "2026-07-30T14:00:00Z",
                "history_role_attack_10": 5.2,
            }
        ]
    )


def test_forward_score_docs_freeze_features_without_outcomes() -> None:
    docs = build_forward_score_docs(
        _score_frame(),
        model_id="model-v3",
        artifact_sha256="artifact-hash",
        training_end="2026-05-24",
        feature_columns=["history_role_attack_10"],
        created_at=datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
    )

    assert len(docs) == 1
    row = docs[0]
    assert row["score_key"] == "model-v3|snap-1|under"
    assert row["feature_values"] == {
        "history_role_attack_10": 5.2
    }
    assert row["market_side_probability"] == pytest.approx(0.52)
    assert row["score_created_at"] < row["match_start_time"]
    assert "actual_value" not in row


def test_forward_score_docs_reject_outcomes_and_future_snapshots() -> None:
    with_outcome = _score_frame()
    with_outcome["actual_value"] = 9.0
    with pytest.raises(ValueError, match="target outcomes"):
        build_forward_score_docs(
            with_outcome,
            model_id="model-v3",
            artifact_sha256="artifact-hash",
            training_end="2026-05-24",
            feature_columns=["history_role_attack_10"],
            created_at=datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
        )

    with pytest.raises(ValueError, match="available before score"):
        build_forward_score_docs(
            _score_frame(),
            model_id="model-v3",
            artifact_sha256="artifact-hash",
            training_end="2026-05-24",
            feature_columns=["history_role_attack_10"],
            created_at=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        )


def test_forward_scores_are_immutable_and_idempotent() -> None:
    docs = build_forward_score_docs(
        _score_frame(),
        model_id="model-v3",
        artifact_sha256="artifact-hash",
        training_end="2026-05-24",
        feature_columns=["history_role_attack_10"],
        created_at=datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
    )
    collection = FakeCollection()

    first = persist_forward_score_docs(collection, docs)
    second = persist_forward_score_docs(collection, docs)

    assert first == {
        "inserted": 1,
        "existing": 0,
        "conflicts": 0,
    }
    assert second == {
        "inserted": 0,
        "existing": 1,
        "conflicts": 0,
    }

    changed = [{**docs[0], "expected_roi_units": 0.5}]
    with pytest.raises(RuntimeError, match="immutable score conflict"):
        persist_forward_score_docs(collection, changed)


def test_forward_score_audit_detects_timing_outcome_and_fingerprint_risks() -> None:
    valid = build_forward_score_docs(
        _score_frame(),
        model_id="model-v3",
        artifact_sha256="artifact-hash",
        training_end="2026-05-24",
        feature_columns=["history_role_attack_10"],
        created_at=datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
    )[0]
    invalid = {
        **valid,
        "score_key": "model-v3|snap-2|under",
        "score_created_at": datetime(
            2026, 7, 30, 15, 0, tzinfo=UTC
        ),
        "actual_value": 9.0,
        "expected_roi_units": 0.5,
    }

    report = audit_forward_score_docs(
        [valid, invalid, valid],
        model_id="model-v3",
    )

    assert report["scores"] == 3
    assert report["valid_scores"] == 1
    assert report["invalid_scores"] == 2
    assert report["timing"]["violations"] == 1
    assert report["timing"]["outcome_mutation_rows"] == 1
    assert report["integrity"]["duplicate_score_keys"] == 1
    assert report["integrity"]["fingerprint_mismatches"] == 1
    assert report["status"] == "warn"
