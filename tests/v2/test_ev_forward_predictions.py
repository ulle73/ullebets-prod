from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version

import pandas as pd
import pytest

from ullebets_v2.ev_model.forward_predictions import (
    build_forward_prediction_docs,
    build_registered_policy_prediction_docs,
    exclude_previously_frozen_matches,
    persist_forward_prediction_docs,
    valid_frozen_match_keys,
    validate_model_runtime,
)


class FakeResult:
    def __init__(self, *, upserted: bool) -> None:
        self.upserted_id = "new" if upserted else None


class FakeCollection:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        return self.rows.get(str(query["prediction_key"]))

    def update_one(
        self,
        query: dict,
        update: dict,
        *,
        upsert: bool,
    ) -> FakeResult:
        key = str(query["prediction_key"])
        if key in self.rows:
            return FakeResult(upserted=False)
        self.rows[key] = dict(update["$setOnInsert"])
        return FakeResult(upserted=True)


def _selection_frame() -> pd.DataFrame:
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
                "predicted_win_probability": 0.58,
                "expected_roi_units": 0.131,
                "odds_snapshot_time": "2026-07-30T10:00:00Z",
                "match_start_time": "2026-07-30T14:00:00Z",
                "history_role_attack_10": 5.2,
            }
        ]
    )


def test_build_forward_prediction_docs_freezes_traceable_prematch_rows() -> None:
    docs = build_forward_prediction_docs(
        _selection_frame(),
        model_id="model-v2",
        artifact_sha256="artifact-hash",
        training_end="2026-05-24",
        feature_columns=["history_role_attack_10"],
        minimum_ev=0.075,
        maximum_ev=0.25,
        created_at=datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
    )

    assert len(docs) == 1
    row = docs[0]
    assert row["prediction_key"] == "model-v2|snap-1|under"
    assert row["selected_odds"] == 1.95
    assert row["prediction_created_before_kickoff"] is True
    assert row["valid_for_forward_evaluation"] is True
    assert row["minimum_ev"] == 0.075
    assert row["maximum_ev"] == 0.25
    assert row["feature_fingerprint_sha256"]
    assert row["prediction_fingerprint_sha256"]
    assert "actual_value" not in row


def test_build_forward_prediction_docs_rejects_predictions_created_after_kickoff() -> None:
    with pytest.raises(ValueError, match="before kickoff"):
        build_forward_prediction_docs(
            _selection_frame(),
            model_id="model-v2",
            artifact_sha256="artifact-hash",
            training_end="2026-05-24",
            feature_columns=["history_role_attack_10"],
            minimum_ev=0.075,
            maximum_ev=0.25,
            created_at=datetime(2026, 7, 30, 15, 0, tzinfo=UTC),
        )


def test_build_forward_prediction_docs_rejects_snapshot_after_prediction_time() -> None:
    frame = _selection_frame()
    frame["odds_snapshot_time"] = "2026-07-30T12:00:00Z"

    with pytest.raises(ValueError, match="available before prediction"):
        build_forward_prediction_docs(
            frame,
            model_id="model-v2",
            artifact_sha256="artifact-hash",
            training_end="2026-05-24",
            feature_columns=["history_role_attack_10"],
            minimum_ev=0.075,
            maximum_ev=0.25,
            created_at=datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
        )


def test_registered_v6_policy_prediction_is_traceable_to_frozen_score() -> None:
    score = {
        "score_key": "v6|snap-1|over",
        "model_id": "v6",
        "artifact_sha256": "artifact-hash",
        "training_end": "2026-05-24",
        "match_key": "m1",
        "sample_key": "m1|cornerKicks|ALL|away",
        "side_key": "m1|cornerKicks|ALL|away|over",
        "snapshot_key": "snap-1",
        "offer_key": "offer-1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "away",
        "direction": "over",
        "line_value": 4.5,
        "offered_odds": 1.95,
        "predicted_win_probability": 0.58,
        "expected_roi_units": 0.131,
        "odds_snapshot_time": datetime(
            2026, 7, 30, 10, 0, tzinfo=UTC
        ),
        "match_start_time": datetime(
            2026, 7, 30, 14, 0, tzinfo=UTC
        ),
        "score_created_at": datetime(
            2026, 7, 30, 11, 0, tzinfo=UTC
        ),
        "valid_for_policy_evaluation": True,
        "invalid_for_model": False,
        "feature_fingerprint_sha256": "feature-hash",
    }

    docs = build_registered_policy_prediction_docs(
        [score],
        policy={
            "policy_id": "v6-primary",
            "model_id": "v6",
            "status": "forward_test_primary",
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "filters": {
                "stat_keys": ["cornerKicks"],
                "scopes": ["away", "total"],
            },
        },
        registry_id="forward_policy_registry_v1",
        registry_fingerprint="registry-hash",
        created_at=datetime(2026, 7, 30, 11, 1, tzinfo=UTC),
    )

    assert len(docs) == 1
    row = docs[0]
    assert row["prediction_key"] == "v6-primary|v6|snap-1|over"
    assert row["prediction_type"] == "ev_registered_score_policy"
    assert row["selection_policy_id"] == "v6-primary"
    assert row["selection_policy_registry_id"] == (
        "forward_policy_registry_v1"
    )
    assert row["selection_policy_registry_fingerprint"] == "registry-hash"
    assert row["source_score_key"] == "v6|snap-1|over"
    assert row["selected_odds"] == 1.95
    assert row["valid_for_forward_evaluation"] is True
    assert row["prediction_fingerprint_sha256"]


def test_registered_policy_prediction_rejects_model_mismatch() -> None:
    with pytest.raises(ValueError, match="does not match score model"):
        build_registered_policy_prediction_docs(
            [
                {
                    "score_key": "v6|snap-1|over",
                    "model_id": "v6",
                }
            ],
            policy={
                "policy_id": "wrong-model",
                "model_id": "v5",
                "status": "forward_test_primary",
                "minimum_ev": 0.075,
                "maximum_ev": 0.25,
            },
            registry_id="registry",
            registry_fingerprint="hash",
        )


def test_persist_forward_predictions_is_immutable_and_idempotent() -> None:
    docs = build_forward_prediction_docs(
        _selection_frame(),
        model_id="model-v2",
        artifact_sha256="artifact-hash",
        training_end="2026-05-24",
        feature_columns=["history_role_attack_10"],
        minimum_ev=0.075,
        maximum_ev=0.25,
        created_at=datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
    )
    collection = FakeCollection()

    first = persist_forward_prediction_docs(collection, docs)
    second = persist_forward_prediction_docs(collection, docs)

    assert first == {"inserted": 1, "existing": 0, "conflicts": 0}
    assert second == {"inserted": 0, "existing": 1, "conflicts": 0}
    assert len(collection.rows) == 1


def test_persist_forward_predictions_rejects_changed_existing_prediction() -> None:
    docs = build_forward_prediction_docs(
        _selection_frame(),
        model_id="model-v2",
        artifact_sha256="artifact-hash",
        training_end="2026-05-24",
        feature_columns=["history_role_attack_10"],
        minimum_ev=0.075,
        maximum_ev=0.25,
        created_at=datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
    )
    collection = FakeCollection()
    persist_forward_prediction_docs(collection, docs)
    changed = [{**docs[0], "expected_roi_units": 0.5}]

    with pytest.raises(RuntimeError, match="immutable prediction conflict"):
        persist_forward_prediction_docs(collection, changed)


def test_validate_model_runtime_rejects_dependency_drift() -> None:
    validate_model_runtime(
        {
            "joblib": version("joblib"),
            "scikit-learn": version("scikit-learn"),
        }
    )

    with pytest.raises(RuntimeError, match="runtime version mismatch"):
        validate_model_runtime({"scikit-learn": "0.0.0"})


def test_exclude_previously_frozen_matches_prevents_cross_model_exposure() -> None:
    snapshots = pd.DataFrame(
        [
            {"match_key": "already-frozen", "snapshot_key": "a"},
            {"match_key": "new-match", "snapshot_key": "b"},
        ]
    )

    filtered, excluded = exclude_previously_frozen_matches(
        snapshots,
        frozen_match_keys={"already-frozen"},
    )

    assert filtered["match_key"].tolist() == ["new-match"]
    assert excluded == 1


def test_valid_frozen_match_keys_rejects_future_snapshot_prediction() -> None:
    rows = [
        {
            "match_key": "valid",
            "odds_snapshot_time": "2026-01-01T10:00:00Z",
            "prediction_created_at": "2026-01-01T11:00:00Z",
            "match_start_time": "2026-01-01T14:00:00Z",
        },
        {
            "match_key": "invalid",
            "odds_snapshot_time": "2026-01-01T12:00:00Z",
            "prediction_created_at": "2026-01-01T11:00:00Z",
            "match_start_time": "2026-01-01T14:00:00Z",
        },
    ]

    assert valid_frozen_match_keys(rows) == {"valid"}
